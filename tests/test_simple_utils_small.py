import numpy as np

from src.simple_utils import convert_numpy_types, format_prediction_response


def test_convert_numpy_scalar_types():
    assert convert_numpy_types(np.int64(7)) == 7
    assert isinstance(convert_numpy_types(np.int64(7)), int)
    assert convert_numpy_types(np.float64(3.5)) == 3.5
    assert isinstance(convert_numpy_types(np.float64(3.5)), float)


def test_convert_numpy_array_and_nested_structures():
    arr = np.array([[1, 2], [3, 4]])
    data = {"a": np.int32(1), "b": [np.float32(2.5), arr]}
    converted = convert_numpy_types(data)

    assert converted == {"a": 1, "b": [2.5, [[1, 2], [3, 4]]]}  # lists, not ndarrays
    assert isinstance(converted["a"], int)
    assert isinstance(converted["b"][0], float)
    assert isinstance(converted["b"][1], list)


def test_format_prediction_response_is_passthrough_with_conversion():
    payload = {"score": np.float64(0.99), "classes": np.array([1, 2, 3])}
    result = format_prediction_response(payload)
    assert result == {"score": 0.99, "classes": [1, 2, 3]}
