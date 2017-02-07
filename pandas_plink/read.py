from __future__ import division, unicode_literals

import sys
from collections import OrderedDict as odict

import pandas as pd

from ._bed_read import read_bed
from ._timeit import TimeIt

PY3 = sys.version_info >= (3, )

if PY3:
    _ord = lambda x: x
else:
    _ord = ord



def read_plink(file_prefix, verbose=True):
    r"""Convert PLINK files into Pandas data frames.

    Args:
        file_prefix (str): Path prefix to the set of PLINK files.
        verbose (bool): `True` for progress information; `False` otherwise.

    Returns:
        tuple: parsed data containing:

            - :class:`pandas.DataFrame`: alleles.
            - :class:`pandas.DataFrame`: samples.
            - :class:`numpy.ndarray`: genotype.

    Examples:

        We have shipped this package with an example so can load and inspect
        by doing

        .. testcode::

            from pandas_plink import read_plink
            from pandas_plink import example_file_prefix
            (bim, fam, bed) = read_plink(example_file_prefix(), verbose=False)
            print(bim.head())
            print(fam.head())
            print(bed.compute())

        Running the above code will print

        .. testoutput::

                                snp   cm a0 a1  i
            chrom pos
            1     45162  rs10399749  0.0  G  C  0
                  45257   rs2949420  0.0  C  T  1
                  45413   rs2949421  0.0  0  0  2
                  46844   rs2691310  0.0  A  T  3
                  72434   rs4030303  0.0  0  G  4

                                 father    mother gender trait  i
            fid      iid
            Sample_1 Sample_1         0         0      1    -9  0
            Sample_2 Sample_2         0         0      2    -9  1
            Sample_3 Sample_3  Sample_1  Sample_2      2    -9  2

            [[2 2 1]
             [2 1 2]
             [3 3 3]
             [3 3 1]
             [2 2 2]
             [2 2 2]
             [2 1 0]
             [2 2 2]
             [1 2 2]
             [2 1 2]]

        Notice the `i` column in bim and fam data frames. It maps to the
        corresponding position of the bed matrix:

        .. testcode::

            from pandas_plink import read_plink
            from pandas_plink import example_file_prefix
            (bim, fam, bed) = read_plink(example_file_prefix(), verbose=False)

            chrom1 = bim.loc[('1', ), :]
            X = bed[chrom1.i,:].compute()
            print(X)

        .. testoutput::

            [[2 2 1]
             [2 1 2]
             [3 3 3]
             [3 3 1]
             [2 2 2]
             [2 2 2]
             [2 1 0]
             [2 2 2]
             [1 2 2]
             [2 1 2]]
    """

    fn = {s: "%s.%s" % (file_prefix, s) for s in ['bed', 'bim', 'fam']}

    with TimeIt("Reading %s..." % fn['bim'], not verbose):
        bim = _read_bim(fn['bim'])
    nmarkers = bim.shape[0]

    with TimeIt("Reading %s..." % fn['fam'], not verbose):
        fam = _read_fam(fn['fam'])
    nsamples = fam.shape[0]

    with TimeIt("Reading %s..." % fn['bed'], not verbose):
        bed = _read_bed(fn['bed'], nsamples, nmarkers)

    return (bim, fam, bed)

def _read_bim(fn):
    header = odict([('chrom', bytes), ('snp', bytes), ('cm', float),
                    ('pos', int), ('a0', bytes), ('a1', bytes)])
    df = pd.read_csv(
        fn,
        delim_whitespace=True,
        header=None,
        names=header.keys(),
        dtype=header,
        compression=None,
        engine='c')

    df['chrom'] = df['chrom'].astype('category')
    df['a0'] = df['a0'].astype('category')
    df['a1'] = df['a1'].astype('category')
    df['i'] = range(df.shape[0])
    df.set_index(['chrom', 'pos'], inplace=True)
    df.sort_index(inplace=True)
    return df


def _read_fam(fn):
    header = odict([('fid', str), ('iid', str), ('father', str),
                    ('mother', str), ('gender', bytes), ('trait', str)])

    df = pd.read_csv(
        fn,
        delim_whitespace=True,
        header=None,
        names=header.keys(),
        dtype=header,
        compression=None,
        index_col=['fid', 'iid'],
        engine='c')

    df['gender'] = df['gender'].astype('category')
    df['i'] = range(df.shape[0])
    df.sort_index(inplace=True)
    return df

def _read_bed(fn, nsamples, nmarkers):
    fn = _ascii_airlock(fn)

    _check_bed_header(fn)
    major = _major_order(fn)

    ncols = nmarkers if major == 'individual' else nsamples
    nrows = nmarkers if major == 'snp' else nsamples

    return read_bed(fn, nrows, ncols)


def _check_bed_header(fn):
    with open(fn, "rb") as f:
        arr = f.read(2)
        ok = _ord(arr[0]) == 108 and _ord(arr[1]) == 27
        if not ok:
            raise ValueError("Invalid BED file: %s." % fn)


def _major_order(fn):
    with open(fn, "rb") as f:
        f.seek(2)
        arr = f.read(1)
        if _ord(arr[0]) == 1:
            return 'snp'
        elif _ord(arr[0]) == 0:
            return 'individual'
        raise ValueError("Couldn't understand matrix layout.")


def _ascii_airlock(v):
    if not isinstance(v, bytes):
        v = v.encode()
    return v