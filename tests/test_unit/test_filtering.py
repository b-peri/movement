"""Testing suite for the filtering module."""

import numpy as np
import pytest
import xarray as xr

from movement.filtering import (
    filter_by_confidence,
    interpolate_over_time,
    log_to_attrs,
)
from movement.sample_data import fetch_sample_data


@pytest.fixture(scope="module")
def sample_dataset():
    """Return a dict containing a single- and a multi-animal sample dataset"""
    return fetch_sample_data("DLC_single-mouse_EPM.predictions.h5")


def test_log_to_attrs(sample_dataset):
    """Test for the ``log_to_attrs()`` decorator. Decorates a mock function and
    checks that ``attrs`` contains all expected values."""

    @log_to_attrs
    def fake_func(ds, arg, kwarg=None):
        return ds

    ds = fake_func(sample_dataset, "test1", kwarg="test2")

    assert "log" in ds.attrs
    assert ds.attrs["log"][0]["operation"] == "fake_func"
    assert (
        ds.attrs["log"][0]["arg_1"] == "test1" and ds.attrs["log"][0]["kwarg"]
    )


def test_interpolate_over_time(sample_dataset):
    """Tests the ``interpolate_over_time`` function by checking
    that the number of nans is decreased when running this function
    on a filtered dataset"""

    ds_filtered = filter_by_confidence(sample_dataset)
    ds_interpolated = interpolate_over_time(ds_filtered)

    def count_nans(ds):
        n_nans = np.count_nonzero(
            np.isnan(
                ds.pose_tracks.sel(
                    individuals="individual_0", keypoints="snout"
                ).values[:, 0]
            )
        )
        return n_nans

    assert count_nans(ds_interpolated) < count_nans(ds_filtered)


def test_filter_by_confidence(sample_dataset, caplog):
    """Tests for the ``filter_by_confidence`` function.
    Checks that the function filters the expected amount of values
    from a known dataset, and tests that this value matches the value
    logged."""

    ds_filtered = filter_by_confidence(sample_dataset)

    assert isinstance(ds_filtered, xr.Dataset)

    n_nans = np.count_nonzero(
        np.isnan(
            ds_filtered.pose_tracks.sel(
                individuals="individual_0", keypoints="snout"
            ).values[:, 0]
        )
    )
    assert n_nans == 3213

    # Check that diagnostics are being logged correctly
    assert "Datapoints Filtered" in caplog.text
    assert f"snout: {n_nans}/{ds_filtered.time.values.shape[0]}" in caplog.text
