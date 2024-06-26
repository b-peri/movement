"""Accessors for extending xarray objects."""

import logging
from typing import ClassVar

import xarray as xr

from movement.analysis import kinematics
from movement.io.validators import ValidPosesDataset

logger = logging.getLogger(__name__)

# Preserve the attributes (metadata) of xarray objects after operations
xr.set_options(keep_attrs=True)


@xr.register_dataset_accessor("move")
class MoveAccessor:
    """A movement-specicific xarray Dataset accessor.

    The xarray Dataset contains the following expected dimensions:
        - ``time``: the number of frames in the video
        - ``individuals``: the number of individuals in the video
        - ``keypoints``: the number of keypoints in the skeleton
        - ``space``: the number of spatial dimensions, either 2 or 3

    Appropriate coordinate labels are assigned to each dimension:
    list of unique names (str) for ``individuals`` and ``keypoints``,
    ['x','y',('z')] for ``space``. The coordinates of the ``time`` dimension
    are in seconds if ``fps`` is provided, otherwise they are in frame numbers.

    The dataset contains two expected data variables (xarray DataArrays):
        - ``position``: with shape (``time``, ``individuals``,
          ``keypoints``, ``space``)
        - ``confidence``: with shape (``time``, ``individuals``, ``keypoints``)

    When accessing a ``.move`` property (e.g. ``displacement``, ``velocity``,
    ``acceleration``) for the first time, the property is computed and stored
    as a data variable with the same name in the dataset. The ``.move``
    accessor can be omitted in subsequent accesses, i.e.
    ``ds.move.displacement`` and ``ds.displacement`` will return the same data
    variable.

    The dataset may also contain following attributes as metadata:
        - ``fps``: the number of frames per second in the video
        - ``time_unit``: the unit of the ``time`` coordinates, frames or
          seconds
        - ``source_software``: the software from which the poses were loaded
        - ``source_file``: the file from which the poses were
          loaded

    Notes
    -----
    Using an accessor is the recommended way to extend xarray objects.
    See [1]_ for more details.

    Methods/properties that are specific to this class can be accessed via
    the ``.move`` accessor, e.g. ``ds.move.validate()``.


    References
    ----------
    .. [1] https://docs.xarray.dev/en/stable/internals/extending-xarray.html

    """

    # Names of the expected dimensions in the dataset
    dim_names: ClassVar[tuple] = (
        "time",
        "individuals",
        "keypoints",
        "space",
    )

    # Names of the expected data variables in the dataset
    var_names: ClassVar[tuple] = (
        "position",
        "confidence",
    )

    def __init__(self, ds: xr.Dataset):
        """Initialize the MoveAccessor."""
        self._obj = ds

    def __getattr__(self, name: str) -> xr.DataArray:
        """Forward requested but undefined attributes to relevant modules.

        This method currently only forwards kinematic property computation
        to the respective functions in the ``kinematics``  module.

        Parameters
        ----------
        name : str
            The name of the attribute to get.

        Returns
        -------
        xarray.DataArray
            The computed attribute value.

        Raises
        ------
        AttributeError
            If the attribute does not exist.

        """

        def method(*args, **kwargs):
            if name.startswith("compute_") and hasattr(kinematics, name):
                self.validate()
                return getattr(kinematics, name)(
                    self._obj.position, *args, **kwargs
                )
            raise AttributeError(
                f"'{self.__class__.__name__}' object has no attribute '{name}'"
            )

        return method

    def validate(self) -> None:
        """Validate the dataset.

        This method checks if the dataset contains the expected dimensions,
        data variables, and metadata attributes. It also ensures that the
        dataset contains valid poses.
        """
        fps = self._obj.attrs.get("fps", None)
        source_software = self._obj.attrs.get("source_software", None)
        try:
            missing_dims = set(self.dim_names) - set(self._obj.dims)
            missing_vars = set(self.var_names) - set(self._obj.data_vars)
            if missing_dims:
                raise ValueError(
                    f"Missing required dimensions: {missing_dims}"
                )
            if missing_vars:
                raise ValueError(
                    f"Missing required data variables: {missing_vars}"
                )
            ValidPosesDataset(
                position_array=self._obj[self.var_names[0]].values,
                confidence_array=self._obj[self.var_names[1]].values,
                individual_names=self._obj.coords[self.dim_names[1]].values,
                keypoint_names=self._obj.coords[self.dim_names[2]].values,
                fps=fps,
                source_software=source_software,
            )
        except Exception as e:
            error_msg = "The dataset does not contain valid poses."
            logger.error(error_msg)
            raise ValueError(error_msg) from e
