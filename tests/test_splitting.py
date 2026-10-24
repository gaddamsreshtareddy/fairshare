import pytest

from logic.splitting import (
    allocate,
    equal_split,
    custom_split,
    percentage_split,
    item_split,
    validate_payers,
)
from logic.validators import ValidationError


def test_uneven_division():
    assert allocate(10000, [1, 1, 1]) == [3334, 3333, 3333]


def test_one_person():
    assert allocate(10000, [1]) == [10000]


def test_zero_total():
    assert allocate(0, [1, 1, 1]) == [0, 0, 0]


def test_weighted_split():
    assert allocate(10, [1, 2]) == [3, 7]


def test_empty_weights_rejected():
    with pytest.raises(ValidationError):
        allocate(10000, [])


def test_equal_split():
    assert equal_split(90000, [1, 2, 3]) == {
        1: 30000,
        2: 30000,
        3: 30000,
    }


def test_equal_split_uneven():
    assert equal_split(10000, [1, 2, 3]) == {
        1: 3334,
        2: 3333,
        3: 3333,
    }


def test_equal_split_empty_members_rejected():
    with pytest.raises(ValidationError):
        equal_split(10000, [])


def test_equal_split_duplicate_members_rejected():
    with pytest.raises(ValidationError):
        equal_split(10000, [1, 2, 1])


def test_equal_split_zero_total_rejected():
    with pytest.raises(ValidationError):
        equal_split(0, [1, 2])

def test_custom_split():
    assert custom_split(
        100000,
        {
            1: 20000,
            2: 30000,
            3: 50000,
        },
    ) == {
        1: 20000,
        2: 30000,
        3: 50000,
    }


def test_custom_split_sum_too_low():
    with pytest.raises(ValidationError):
        custom_split(
            100000,
            {
                1: 20000,
                2: 30000,
                3: 40000,
            },
        )


def test_custom_split_sum_too_high():
    with pytest.raises(ValidationError):
        custom_split(
            100000,
            {
                1: 20000,
                2: 30000,
                3: 60000,
            },
        )


def test_custom_split_negative_share():
    with pytest.raises(ValidationError):
        custom_split(
            100000,
            {
                1: 20000,
                2: -10000,
                3: 90000,
            },
        )

def test_percentage_split():
    assert percentage_split(
        100000,
        {
            1: "20",
            2: "30",
            3: "50",
        },
    ) == {
        1: 20000,
        2: 30000,
        3: 50000,
    }


def test_percentage_split_with_two_decimal_places():
    result = percentage_split(
        100000,
        {
            1: "33.34",
            2: "33.33",
            3: "33.33",
        },
    )

    assert sum(result.values()) == 100000


def test_percentage_split_99_99_rejected():
    with pytest.raises(ValidationError):
        percentage_split(
            100000,
            {
                1: "33.33",
                2: "33.33",
                3: "33.33",
            },
        )


def test_percentage_split_below_100_rejected():
    with pytest.raises(ValidationError):
        percentage_split(100000, {1: "99.9"})


def test_percentage_split_above_100_rejected():
    with pytest.raises(ValidationError):
        percentage_split(100000, {1: "100.1"})


def test_percentage_split_three_decimal_places_rejected():
    with pytest.raises(ValidationError):
        percentage_split(100000, {1: "50.001", 2: "49.999"})


def test_percentage_split_over_100_rejected():
    with pytest.raises(ValidationError):
        percentage_split(
            100000,
            {
                1: "150",
            },
        )

def test_item_split():
    total, shares = item_split(
        [
            (60000, [1, 2]),
            (30000, [2, 3]),
            (30000, [1]),
        ]
    )

    assert total == 120000
    assert shares == {
        1: 60000,
        2: 45000,
        3: 15000,
    }


def test_item_split_no_consumers_rejected():
    with pytest.raises(ValidationError):
        item_split([(60000, [])])


def test_item_split_duplicate_consumers_rejected():
    with pytest.raises(ValidationError):
        item_split([(60000, [1, 1])])


def test_item_split_zero_amount_rejected():
    with pytest.raises(ValidationError):
        item_split([(0, [1])])


def test_item_split_empty_items_rejected():
    with pytest.raises(ValidationError):
        item_split([])


def test_validate_one_payer():
    assert validate_payers(
        120000,
        {1: 120000},
    ) == {1: 120000}


def test_validate_two_payers():
    assert validate_payers(
        120000,
        {
            1: 70000,
            2: 50000,
        },
    ) == {
        1: 70000,
        2: 50000,
    }


def test_validate_payers_mismatch():
    with pytest.raises(ValidationError):
        validate_payers(
            120000,
            {
                1: 70000,
                2: 40000,
            },
        )


def test_validate_zero_payer():
    with pytest.raises(ValidationError):
        validate_payers(
            120000,
            {
                1: 120000,
                2: 0,
            },
        )