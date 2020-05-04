import numpy as np
from .._shared.utils import deprecated
from ._remap import _map_array


def join_segmentations(s1, s2):
    """Return the join of the two input segmentations.

    The join J of S1 and S2 is defined as the segmentation in which two
    voxels are in the same segment if and only if they are in the same
    segment in *both* S1 and S2.

    Parameters
    ----------
    s1, s2 : numpy arrays
        s1 and s2 are label fields of the same shape.

    Returns
    -------
    j : numpy array
        The join segmentation of s1 and s2.

    Examples
    --------
    >>> from skimage.segmentation import join_segmentations
    >>> s1 = np.array([[0, 0, 1, 1],
    ...                [0, 2, 1, 1],
    ...                [2, 2, 2, 1]])
    >>> s2 = np.array([[0, 1, 1, 0],
    ...                [0, 1, 1, 0],
    ...                [0, 1, 1, 1]])
    >>> join_segmentations(s1, s2)
    array([[0, 1, 3, 2],
           [0, 5, 3, 2],
           [4, 5, 5, 3]])
    """
    if s1.shape != s2.shape:
        raise ValueError("Cannot join segmentations of different shape. " +
                         "s1.shape: %s, s2.shape: %s" % (s1.shape, s2.shape))
    s1 = relabel_sequential(s1)[0]
    s2 = relabel_sequential(s2)[0]
    j = (s2.max() + 1) * s1 + s2
    j = relabel_sequential(j)[0]
    return j


def relabel_sequential(label_field, offset=1):
    """Relabel arbitrary labels to {`offset`, ... `offset` + number_of_labels}.

    This function also returns the forward map (mapping the original labels to
    the reduced labels) and the inverse map (mapping the reduced labels back
    to the original ones).

    Parameters
    ----------
    label_field : numpy array of int, arbitrary shape
        An array of labels, which must be non-negative integers.
    offset : int, optional
        The return labels will start at `offset`, which should be
        strictly positive.

    Returns
    -------
    relabeled : numpy array of int, same shape as `label_field`
        The input label field with labels mapped to
        {offset, ..., number_of_labels + offset - 1}.
        The data type will be the same as `label_field`, except when
        offset + number_of_labels causes overflow of the current data type.
    forward_map : ArrayMap
        The map from the original label space to the returned label
        space. Can be used to re-apply the same mapping. See examples
        for usage. The output data type will be the same as `relabeled`.
    inverse_map : ArrayMap
        The map from the new label space to the original space. This
        can be used to reconstruct the original label field from the
        relabeled one. The output data type will be the same as `label_field`.

    Notes
    -----
    The label 0 is assumed to denote the background and is never remapped.

    The forward map can be extremely big for some inputs, since its
    length is given by the maximum of the label field. However, in most
    situations, ``label_field.max()`` is much smaller than
    ``label_field.size``, and in these cases the forward map is
    guaranteed to be smaller than either the input or output images.

    Examples
    --------
    >>> from skimage.segmentation import relabel_sequential
    >>> label_field = np.array([1, 1, 5, 5, 8, 99, 42])
    >>> relab, fw, inv = relabel_sequential(label_field)
    >>> relab
    array([1, 1, 2, 2, 3, 5, 4])
    >>> print(fw)
    ArrayMap:
      1 → 1
      5 → 2
      8 → 3
      42 → 4
      99 → 5
    >>> np.array(fw)
    array([0, 1, 0, 0, 0, 2, 0, 0, 3, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
           0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 4, 0,
           0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
           0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
           0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 5])
    >>> np.array(inv)
    array([ 0,  1,  5,  8, 42, 99])
    >>> (fw[label_field] == relab).all()
    True
    >>> (inv[relab] == label_field).all()
    True
    >>> relab, fw, inv = relabel_sequential(label_field, offset=5)
    >>> relab
    array([5, 5, 6, 6, 7, 9, 8])
    """
    if offset <= 0:
        raise ValueError("Offset must be strictly positive.")
    if np.min(label_field) < 0:
        raise ValueError("Cannot relabel array that contains negative values.")
    offset = int(offset)
    in_vals = np.unique(label_field)
    if in_vals[0] == 0:
        # always map 0 to 0
        out_vals = np.concatenate(
            [[0], np.arange(offset, offset+len(in_vals)-1)]
        )
    else:
        out_vals = np.arange(offset, offset+len(in_vals))
    input_type = label_field.dtype

    # Some logic to determine the output type:
    #  - we don't want to return a smaller output type than the input type,
    #  ie if we get uint32 as labels input, don't return a uint8 array.
    #  - but, in some cases, using the input type could result in overflow. The
    #  input type could be a signed integer (e.g. int32) but
    #  `np.min_scalar_type` will always return an unsigned type. We check for
    #  that by casting the largest output value to the input type. If it is
    #  unchanged, we use the input type, else we use the unsigned minimum
    #  required type
    required_type = np.min_scalar_type(out_vals[-1])
    if input_type.itemsize < required_type.itemsize:
        output_type = required_type
    else:
        if input_type.type(out_vals[-1]) == out_vals[-1]:
            output_type = input_type
        else:
            output_type = required_type
    out_array = np.empty(label_field.shape, dtype=output_type)
    out_vals = out_vals.astype(output_type)
    map_array(label_field, in_vals, out_vals, out=out_array)
    fw_map = ArrayMap(in_vals, out_vals)
    inv_map = ArrayMap(out_vals, in_vals)
    return out_array, fw_map, inv_map


def map_array(input_arr, input_vals, output_vals, out=None):
    """Map values from input array from input_vals to output_vals.

    Parameters
    ----------
    input_arr : array of int, shape (M[, N][, P][, ...])
        The input label image.
    input_vals : array of int, shape (N,)
        The values to map from.
    output_vals : array, shape (N,)
        The values to map to.
    out: array, same shape as `input_arr`
        The output array. Will be created if not provided. It should
        have the same dtype as `output_vals`.

    Returns
    -------
    out : array, same shape as `input_arr`
        The array of mapped values.
    """

    if not np.issubdtype(input_arr.dtype, np.integer):
        raise TypeError(
            'The dtype of an array to be remapped should be integer.'
        )
    # We ravel the input array for simplicity of iteration in Cython:
    orig_shape = input_arr.shape
    # NumPy docs for `np.ravel()` says:
    # "When a view is desired in as many cases as possible, 
    # arr.reshape(-1) may be preferable."
    input_arr = input_arr.reshape(-1)
    if out is None:
        out = np.empty(orig_shape, dtype=output_vals.dtype)
    elif out.shape != orig_shape:
        raise ValueError(
            'If out array is provided, it should have the same shape as '
            f'the input array. Input array has shape {orig_shape}, provided '
            f'output array has shape {out.shape}.'
        )
    try:
        out_view = out.view()
        out_view.shape = (-1,)  # no-copy reshape/ravel
    except AttributeError:  # if out strides are not compatible with 0-copy
        raise ValueError(
            'If out array is provided, it should be either contiguous '
            f'or 1-dimensional. Got array with shape {out.shape} and '
            f'strides {out.strides}.'
        )

    # ensure all arrays have matching types before sending to Cython
    input_vals = input_vals.astype(input_arr.dtype, copy=False)
    output_vals = output_vals.astype(out.dtype, copy=False)
    _map_array(input_arr, out_view, input_vals, output_vals)
    return out


class ArrayMap:
    """Class designed to mimic mapping by NumPy array indexing.

    This class is designed to replicate the use of NumPy arrays for mapping
    values with indexing:

    >>> values = np.array([0.25, 0.5, 1.0])
    >>> indices = np.array([[0, 0, 1], [2, 2, 1]])
    >>> values[indices]
    array([[0.25, 0.25, 0.5 ],
           [1.  , 1.  , 0.5 ]])

    The issue with this indexing is that you need a very large ``values``
    array if the values in the ``indices`` array are large.

    >>> values = np.array([0.25, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1.0])
    >>> indices = np.array([[0, 0, 10], [0, 10, 10]])
    >>> values[indices]
    array([[0.25, 0.25, 1.  ],
           [0.25, 1.  , 1.  ]])

    Using this class, the approach is similar, but there is no need to
    create a large values array:

    >>> in_indices = np.array([0, 10])
    >>> out_values = np.array([0.25, 1.0])
    >>> values = ArrayMap(in_indices, out_values)
    >>> values
    ArrayMap(array([ 0, 10]), array([0.25, 1.  ]))
    >>> print(values)
    ArrayMap:
      0 → 0.25
      10 → 1.0
    >>> indices = np.array([[0, 0, 10], [0, 10, 10]])
    >>> values[indices]
    array([[0.25, 0.25, 1.  ],
           [0.25, 1.  , 1.  ]])

    Parameters
    ----------
    in_values : array of int, shape (N,)
        The source values from which to map.
    out_values : array, shape (N,)
        The destination values from which to map.
    """
    def __init__(self, in_values, out_values):
        self.in_values = in_values
        self.out_values = out_values
        self._max_str_lines = 4
        self._array = None

    def __len__(self):
        """Return one more than the maximum label value being remapped."""
        return np.max(self.in_values) + 1

    def __array__(self, dtype=None):
        """Return an array that behaves like the arraymap when indexed.
        
        This array can be very large: it is the size of the largest value
        in the ``in_vals`` array, plus one.
        """
        if dtype is None:
            dtype = self.out_values.dtype
        output = np.zeros(np.max(self.in_values) + 1, dtype=dtype)
        output[self.in_values] = self.out_values
        return output

    @property
    def dtype(self):
        return self.out_values.dtype

    def __repr__(self):
        return f'ArrayMap({repr(self.in_values)}, {repr(self.out_values)})'

    def __str__(self):
        if len(self.in_values) <= self._max_str_lines + 1:
            rows = range(len(self.in_values))
            string = '\n'.join(
                ['ArrayMap:'] +
                [f'  {self.in_values[i]} → {self.out_values[i]}' for i in rows]
            )
        else:
            rows0 = list(range(0, self._max_str_lines // 2))
            rows1 = list(range(-self._max_str_lines // 2, 0))
            string = '\n'.join(
                ['ArrayMap:'] +
                [f'  {self.in_values[i]} → {self.out_values[i]}'
                 for i in rows0] +
                ['  ...'] +
                [f'  {self.in_values[i]} → {self.out_values[i]}'
                 for i in rows1]
            )
        return string

    def __call__(self, arr):
        return self.__getitem__(arr)

    def __getitem__(self, index):
        scalar = np.isscalar(index)
        if scalar:
            index = np.array([index])
        elif isinstance(index, slice):
            start = index.start or 0  # treat None or 0 the same way
            stop = (index.stop
                    if index.stop is not None
                    else len(self))
            step = index.step
            index = np.arange(start, stop, step)
        if index.dtype == bool:
            index = np.flatnonzero(index)

        out = map_array(
            index,
            self.in_values.astype(index.dtype, copy=False),
            self.out_values,
        )

        if scalar:
            out = out[0]
        return out

    def __setitem__(self, indices, values):
        if self._array is None:
            self._array = self.__array__()
        self._array[indices] = values
        self.in_values = np.flatnonzero(self._array)
        self.out_values = self._array[self.in_values]
