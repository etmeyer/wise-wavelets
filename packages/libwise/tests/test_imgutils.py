import datetime
import warnings

import numpy as np
import pytest
from astropy.io import fits as pyfits
from libwise import imgutils, nputils


def test_gaussien_cylinder_no_arg():
    try:
        imgutils.gaussian_cylinder(100)
        assert False
    except ValueError:
        pass


def do_gaussien_cylinder(exp, size, nsigma=None, width=None,
                         center_offset=0, angle=None):
    res = imgutils.gaussian_cylinder(size, nsigma=nsigma,
                                     width=width, center_offset=center_offset,
                                     angle=angle)
    print((res * 1000).astype(int))
    print(exp)
    return np.equal(exp, (res * 1000).astype(int)).all()


def test_gaussien_cylinder_nsigma():
    nsigma = 2
    exp = np.array([[278, 278, 278, 278, 278],
                    [ 726, 726, 726, 726, 726],
           [1000, 1000, 1000, 1000, 1000],
           [726, 726, 726, 726, 726],
           [278, 278, 278, 278, 278]])

    assert do_gaussien_cylinder(exp, 5, nsigma=nsigma)


def test_gaussien_cylinder_nsigma_fct():
    nsigma = lambda y: 1 + y
    exp = np.array([[726, 278, 56, 5, 0],
             [923, 726, 486, 278, 135],
             [1000, 1000, 1000, 1000, 1000],
             [923, 726, 486, 278, 135],
             [726, 278, 56, 5, 0]])

    assert do_gaussien_cylinder(exp, 5, nsigma=nsigma)
    assert not do_gaussien_cylinder(exp, 5, nsigma=nsigma, width=10)


def test_gaussien_cylinder_width():
    width = 2
    exp = np.array([[  62, 62, 62, 62, 62],
                 [ 500, 500, 500, 500, 500],
                 [1000, 1000, 1000, 1000, 1000],
                 [ 500, 500, 500, 500, 500],
                 [  62, 62, 62, 62, 62]])

    assert do_gaussien_cylinder(exp, 5, width=width)
    # precedence over nsigma
    assert do_gaussien_cylinder(exp, 5, width=width, nsigma=10)

    exp = np.vstack(([1] * 5, exp))
    exp = np.hstack((exp, exp[:,-2:-1]))

    assert do_gaussien_cylinder(exp, 6, width=width)


def test_gaussien_cylinder_width_fct():
    width = lambda y: 1 + y
    exp = np.array([[   0, 62, 291, 500, 641],
         [  62, 500, 734, 840, 895],
         [1000, 1000, 1000, 1000, 1000],
         [  62, 500, 734, 840, 895],
         [   0, 62, 291, 500, 641]])

    assert do_gaussien_cylinder(exp, 5, width=width)


def test_gaussien_cylinder_fct():
    width = 2
    fct = lambda y: 0.5 * y

    exp = np.array([[  62, 210, 500, 840, 1000],
             [ 500, 840, 1000, 840, 500],
             [1000, 840, 500, 210, 62],
             [ 500, 210, 62, 13, 1],
             [  62, 13, 1, 0, 0]])

    assert do_gaussien_cylinder(exp, 5, width=width, center_offset=fct)

    angle = np.pi / 4.

    exp = np.array([[  62, 500, 1000, 500, 62],
             [ 500, 1000, 500, 62, 1],
             [1000, 500, 62, 1, 0],
             [ 500, 62, 1, 0, 0],
             [  62, 1, 0, 0, 0]])

    assert do_gaussien_cylinder(exp, 5, width=width, angle=angle)


def test_gaussien_no_arg():
    try:
        imgutils.gaussian(5)
        assert False
    except ValueError:
        pass


def do_gaussien(exp, size, nsigma=None, width=None):
    res = imgutils.gaussian(size, nsigma=nsigma, width=width)
    return np.equal(exp, (res * 1000).astype(int)).all()


def test_gaussien_nsigma():
    nsigma = 2
    exp = np.array([[  18, 82, 135, 82, 18],
             [  82, 367, 606, 367, 82],
             [ 135, 606, 1000, 606, 135],
             [  82, 367, 606, 367, 82],
             [  18, 82, 135, 82, 18]])

    assert do_gaussien(exp, 5, nsigma=nsigma)
    assert not do_gaussien(exp, 5, nsigma=nsigma, width=10)


def test_gaussien_width():
    width = 2
    exp = np.array([[   3, 31, 62, 31, 3],
             [  31, 250, 500, 250, 31],
             [  62, 500, 1000, 500, 62],
             [  31, 250, 500, 250, 31],
             [   3, 31, 62, 31, 3]])

    assert do_gaussien(exp, 5, width=width)
    assert do_gaussien(exp, 5, nsigma=10, width=width)


def test_gaussien_width_even():
    width = 2
    exp = np.array([[   3, 31, 62, 31],
             [  31, 250, 500, 250],
             [  62, 500, 1000, 500],
             [  31, 250, 500, 250]])

    assert do_gaussien(exp, 4, width=width)
    assert do_gaussien(exp, 4, nsigma=10, width=width)


def _write_fits(tmp_path, data, axis_types, axis_units, crval, cdelt, crpix,
                extra_header=None):
    naxis = data.ndim
    header = pyfits.Header()
    header['SIMPLE'] = True
    header['BITPIX'] = -64
    header['NAXIS'] = naxis
    # FITS axis order is the reverse of numpy axis order.
    for i, n in enumerate(reversed(data.shape), start=1):
        header['NAXIS%d' % i] = n
    for i, (ctype, cunit, val, delt, pix) in enumerate(
        zip(axis_types, axis_units, crval, cdelt, crpix), start=1
    ):
        header['CTYPE%d' % i] = ctype
        header['CUNIT%d' % i] = cunit
        header['CRVAL%d' % i] = val
        header['CDELT%d' % i] = delt
        header['CRPIX%d' % i] = pix
    if extra_header:
        for k, v in extra_header.items():
            header[k] = v
    hdu = pyfits.PrimaryHDU(data=data, header=header)
    path = tmp_path / "test.fits"
    hdu.writeto(path, overwrite=True)
    return str(path)


def test_fits_loader_handles_4d_casa_cube(tmp_path):
    # CASA-exported continuum images come as (Stokes, freq, Dec, RA) with
    # the spectral and Stokes axes length 1.
    data = np.arange(80 * 60, dtype=np.float32).reshape(1, 1, 60, 80)
    path = _write_fits(
        tmp_path,
        data,
        axis_types=['RA---SIN', 'DEC--SIN', 'FREQ', 'STOKES'],
        axis_units=['deg', 'deg', 'Hz', ''],
        crval=[180.0, 25.0, 1.4e9, 1.0],
        cdelt=[-1e-4, 1e-4, 1e6, 1.0],
        crpix=[40.0, 30.0, 1.0, 1.0],
        extra_header={'BMAJ': 2e-4, 'BMIN': 1e-4, 'BPA': 30.0,
                      'BUNIT': 'JY/BEAM', 'OBJECT': 'TEST',
                      'DATE-OBS': '2024-01-15'},
    )

    img = imgutils.FitsImage(path)

    assert img.data.shape == (60, 80)
    assert img.data.dtype == np.float64
    assert np.allclose(img.data, data[0, 0].astype(np.float64))
    # Celestial WCS should expose only the 2 sky axes — no freq/Stokes pollution.
    assert img.wcs.naxis == 2
    assert img.get_object() == 'TEST'


def test_fits_loader_squeezes_3d_data(tmp_path):
    # Some pipelines emit NAXIS=3 (freq or Stokes axis dropped, the other
    # length 1). The loader should squeeze that down too.
    data = np.arange(50 * 40, dtype=np.float32).reshape(1, 50, 40)
    path = _write_fits(
        tmp_path,
        data,
        axis_types=['RA---SIN', 'DEC--SIN', 'FREQ'],
        axis_units=['deg', 'deg', 'Hz'],
        crval=[180.0, 25.0, 1.4e9],
        cdelt=[-1e-4, 1e-4, 1e6],
        crpix=[20.0, 25.0, 1.0],
    )

    img = imgutils.FitsImage(path)

    assert img.data.shape == (50, 40)
    assert img.wcs.naxis == 2


def test_fits_loader_still_handles_2d(tmp_path):
    # Legacy AIPS-style 2D files (like the MOJAVE 3C120 data) must still work.
    data = np.arange(30 * 20, dtype=np.float32).reshape(30, 20)
    path = _write_fits(
        tmp_path,
        data,
        axis_types=['RA---SIN', 'DEC--SIN'],
        axis_units=['deg', 'deg'],
        crval=[180.0, 25.0],
        cdelt=[-1e-4, 1e-4],
        crpix=[10.0, 15.0],
    )

    img = imgutils.FitsImage(path)

    assert img.data.shape == (30, 20)
    assert img.wcs.naxis == 2


def test_fits_loader_rejects_real_cube(tmp_path):
    # A genuine cube (multi-channel) cannot be reduced to 2D — surface a
    # clear error rather than silently picking one plane.
    data = np.zeros((1, 4, 30, 20), dtype=np.float32)
    path = _write_fits(
        tmp_path,
        data,
        axis_types=['RA---SIN', 'DEC--SIN', 'FREQ', 'STOKES'],
        axis_units=['deg', 'deg', 'Hz', ''],
        crval=[180.0, 25.0, 1.4e9, 1.0],
        cdelt=[-1e-4, 1e-4, 1e6, 1.0],
        crpix=[10.0, 15.0, 1.0, 1.0],
    )

    with pytest.raises(ValueError, match="non-trivial axes"):
        imgutils.FitsImage(path)


@pytest.mark.skip(reason="Test uses imgutils.Region([5, 5]).add_rectangle(...) — that constructor takes a pyregion filename, and add_rectangle/get_mask methods don't exist on Region")
def test_mask():
    m1 = np.ones([5, 5])

    m2 = np.zeros([5, 5])
    m2[2:3, 2:4] = 1

    m3 = np.zeros([5, 5])
    m3[1:3, 0:] = 1

    assert np.allclose(m1, imgutils.Mask(m1).get_mask())
    assert imgutils.Mask(m2).get_area() == m2.sum()

    assert np.allclose(imgutils.Mask(m1).intersection(imgutils.Mask(m2)).get_mask(), m2)

    assert np.allclose(imgutils.Mask(m2).union(imgutils.Mask(m3)).get_mask(), (m2 + m3).astype(bool).astype(int))

    assert np.allclose(imgutils.Mask.from_mask_list([imgutils.Mask(m2), imgutils.Mask(m3)]).get_mask(), (m2 + m3).astype(bool).astype(int))

    region1 = imgutils.Region([5, 5])
    region1.add_rectangle([2, 2], [2, 3])

    assert np.allclose(region1.get_mask(), m2)

    region2 = imgutils.Region([5, 5])
    region2.add_rectangle([1, 0], [2, 4])

    assert np.allclose(region2.get_mask(), m3)

    region2.add_rectangle([2, 2], [2, 3])

    assert np.allclose(region2.get_mask(), (m2 + m3).astype(bool).astype(int))


def test_region_image():
    m2 = np.zeros([5, 5])
    m2[2:3, 2:4] = 1

    img1 = imgutils.gaussian(100, width=6, angle=-0.5, center=[70, 55])
    img1[img1 < 0.1] = 0
    seg1, index = nputils.crop_threshold(img1, output_index=True)

    region1 = imgutils.ImageRegion(img1, index)

    assert np.allclose(region1.get_region(), seg1)
    assert np.allclose(region1.get_data(), img1)

    assert region1.get_shape() == img1.shape
    assert region1.get_shift() == [0, 0]
    assert region1.get_index() == index
    assert list(region1.get_center()) == [70, 55]

    region1.set_shift([-5, -4])

    img2 = imgutils.gaussian(100, width=6, angle=-0.5, center=[65, 51])
    img2[img2 < 0.1] = 0
    seg2, index2 = nputils.crop_threshold(img2, output_index=True)

    assert np.allclose(region1.get_region(), seg2)
    assert np.allclose(region1.get_data(), img2)
    assert list(region1.get_center()) == [65, 51], region1.get_center()

    region1.set_shift([-70, 10])

    img3 = imgutils.gaussian(100, width=6, angle=-0.5, center=[0, 65])
    img3[img3 < 0.1] = 0
    seg3, index = nputils.crop_threshold(img3, output_index=True)

    assert np.allclose(region1.get_region(), seg3)
    assert np.allclose(region1.get_data(), img3)
    assert list(region1.get_center()) == [0 + 6 // 2, 65]

    region1.set_shift([30, 10])

    img3 = imgutils.gaussian(100, width=6, angle=-0.5, center=[100, 65])
    img3[img3 < 0.1] = 0
    seg3, index = nputils.crop_threshold(img3, output_index=True)

    assert np.allclose(region1.get_region(), seg3)
    assert np.allclose(region1.get_data(), img3)
    # Image is indexed 0..99; max valid index 99. Visible region after the
    # out-of-bounds shift spans rows [95..99] (shape 5), centered at
    # 95 + (5-1)//2 = 97 — not 98 as a naive `100 - 5/2` would suggest.
    assert list(region1.get_center()) == [99 - (5 - 1) // 2, 65], (region1.get_center(), seg3.shape)

    region1.set_shift([20, 10])

    img3 = imgutils.gaussian(100, width=6, angle=-0.5, center=[90, 65])
    img3[img3 < 0.1] = 0
    seg3, index = nputils.crop_threshold(img3, output_index=True)

    assert np.allclose(region1.get_region(), seg3)
    assert np.allclose(region1.get_data(), img3)
    assert list(region1.get_center()) == [90, 65]

    region2 = imgutils.ImageRegion(img2, index2)

    builder = imgutils.ImageBuilder()
    builder.add(region1)
    builder.add(region2)

    res = builder.get()

    seg4, index = nputils.crop_threshold(img2 + img3, output_index=True)

    assert res.get_shape() == img1.shape
    assert np.allclose(res.get_data(), img3 + img2)
    assert np.allclose(res.get_region(), seg4)
    assert res.get_index() == index


@pytest.mark.skip(reason="ImageRegion.zoom(center, shape) does not exist in upstream — Image.zoom(factor) is the inherited signature")
def test_image_region_zoom():

    def do_test(c, sa, ri, sz):
        cx, cy = c
        a = np.zeros(sa)
        a[cx, cy] = 1
        print(a)

        a = imgutils.ImageRegion(a, ri)
        print(a.get_region())

        za = a.zoom(c, sz)
        shift = c - za.get_center()
        zcx, zcy = np.array(za.get_region().shape) // 2 + shift
        print(za.get_region())
        print(shift, zcx, zcy)
        assert za.get_region()[int(zcx), int(zcy)] == 1

    do_test([2, 3], [8, 9], [1, 0, 7, 8], [2, 2])
    do_test([2, 3], [5, 6], [1, 0, 4, 5], [3, 3])
    do_test([2, 3], [5, 6], [1, 0, 4, 5], [5, 5])
    do_test([2, 3], [5, 6], [1, 0, 4, 5], [5, 6])
    do_test([1, 1], [5, 6], [1, 0, 4, 5], [5, 6])
    do_test([1, 1], [5, 6], [1, 0, 4, 5], [4, 3])
    do_test([3, 4], [5, 6], [1, 0, 4, 5], [5, 6])
    do_test([3, 4], [5, 6], [1, 0, 4, 5], [4, 4])


def _write_minimal_fits(path, date_obs):
    data = np.zeros((4, 4), dtype=np.float32)
    hdu = pyfits.PrimaryHDU(data=data)
    hdu.header['DATE-OBS'] = date_obs
    hdu.writeto(str(path), overwrite=True)
    return str(path)


def test_fast_sorted_fits_mixes_date_only_and_iso_with_time(tmp_path):
    # Regression for issue #10: ISO-with-time DATE-OBS (common in VLBA
    # correlator output) used to return None from get_fits_epoch_fast,
    # which then crashed sorted() with a NoneType/datetime TypeError.
    iso = _write_minimal_fits(tmp_path / "iso.fits", '2019-03-15T12:34:56.7')
    date_only = _write_minimal_fits(tmp_path / "date_only.fits", '2018-01-25')

    out = imgutils.fast_sorted_fits([iso, date_only])

    assert list(out) == [date_only, iso]


def test_fast_sorted_fits_skips_unparseable_dates(tmp_path):
    # Defense in depth: if a DATE-OBS still eludes the format list (e.g.
    # timezone-suffixed forms like '...Z' or '...+00:00'), drop that file
    # with a warning rather than crash the whole batch.
    good = _write_minimal_fits(tmp_path / "good.fits", '2018-01-25')
    bad = _write_minimal_fits(tmp_path / "bad.fits", '2019-03-15T12:34:56Z')

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        out = imgutils.fast_sorted_fits([good, bad])

    assert list(out) == [good]
    assert any('DATE-OBS' in str(w.message) and 'bad.fits' in str(w.message)
               for w in caught)


def test_fast_sorted_fits_iso_ordering(tmp_path):
    # Two ISO-with-time files should sort chronologically by their full
    # timestamp, not just the date portion.
    early = _write_minimal_fits(tmp_path / "early.fits", '2019-03-15T01:00:00')
    late = _write_minimal_fits(tmp_path / "late.fits", '2019-03-15T23:00:00')

    out = imgutils.fast_sorted_fits([late, early])

    assert list(out) == [early, late]


def test_get_fits_epoch_fast_parses_iso_with_subseconds(tmp_path):
    path = _write_minimal_fits(tmp_path / "iso.fits", '2019-03-15T12:34:56.7')

    epoch = imgutils.get_fits_epoch_fast(path)

    assert epoch == datetime.datetime(2019, 3, 15, 12, 34, 56, 700000)


def test_get_ensemble_index():
    img1 = imgutils.ImageRegion(np.zeros([20, 20]), (2, 5, 3, 6))
    img2 = imgutils.ImageRegion(np.zeros([20, 20]), (3, 10, 1, 5))
    img3 = imgutils.ImageRegion(np.zeros([20, 20]), (2, 9, 4, 2))
    assert imgutils.get_ensemble_index([img1, img2, img3]) == [2, 5, 4, 6]

    img1 = imgutils.ImageRegion(np.zeros([20]), (2, 5))
    img2 = imgutils.ImageRegion(np.zeros([20]), (3, 10))
    img3 = imgutils.ImageRegion(np.zeros([20]), (2, 9))
    assert imgutils.get_ensemble_index([img1, img2, img3]) == [2, 10]


def zip_index():
    assert imgutils.zip_index((2, 3, 5, 7)) == ((2, 5), (3, 7))
    assert imgutils.zip_index((2, 5)) == ((2, 5))


@pytest.mark.skip(reason="Upstream test ends with assert False — incomplete debug stub")
def test_join_image_region():
    img1 = imgutils.ImageRegion(np.ones([6, 6]) * 1, (2, 3, 5, 6))
    img2 = imgutils.ImageRegion(np.ones([6, 6]) * 2, (3, 0, 6, 4))
    img3 = imgutils.ImageRegion(np.ones([6, 6]) * 3, (0, 2, 4, 4))

    builder = imgutils.ImageBuilder()
    builder.add(img1)
    builder.add(img2)
    builder.add(img3)

    print(builder.get().get_region())

    assert np.allclose(builder.get().get_region(), imgutils.join_image_region([img1, img2, img3], [6, 6]))
    # assert imgutils.get_ensemble_index([img1, img2, img3]) == [0, 0, 7, 7]

    print(imgutils.join_image_region([img1, img2, img3], [12, 12]))
    print(imgutils.join_image_region([img1, img2, img3], [7, 7]))

    assert False


@pytest.mark.skip(reason="Upstream test ends with assert False and constructs StackedImage from a bare ndarray (which calls .get_epoch()) — incomplete debug stub")
def test_stack_image():
    a = imgutils.Image(np.ones([5, 5]))
    b = imgutils.Image(np.ones([5, 5]) * 2)

    stacked = imgutils.StackedImage(a.data)
    stacked.add(b)
    print(stacked.data)

    stack_mgr = imgutils.StackedImageBuilder()
    stack_mgr.add(a)
    stack_mgr.add(b)
    print(stack_mgr.get().data)

    assert False
