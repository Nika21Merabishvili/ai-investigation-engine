# tests/test_search.py
import pytest

from app.search import rrf


def test_rrf_hand_computed():
    dense = [10, 20, 30]     # 10 is rank 1, 20 rank 2, 30 rank 3
    keyword = [20, 40, 10]   # 20 is rank 1, 40 rank 2, 10 rank 3
    # k = 60, both weights 1.0:
    #   20: 1/62 + 1/61 = 0.032522   (2nd in dense, 1st in keyword)
    #   10: 1/61 + 1/63 = 0.032266   (1st in dense, 3rd in keyword)
    #   40: 1/62        = 0.016129   (keyword only)
    #   30: 1/63        = 0.015873   (dense only)
    result = rrf([dense, keyword], k=60)

    assert [chunk_id for chunk_id, _ in result] == [20, 10, 40, 30]
    assert [score for _, score in result] == pytest.approx(
        [1/62 + 1/61, 1/61 + 1/63, 1/62, 1/63]
    )


def test_rrf_weights_change_the_order():
    # Same lists, dense counts double:
    #   10: 2/61 + 1/63 = 0.048660
    #   20: 2/62 + 1/61 = 0.048652
    #   30: 2/63        = 0.031746
    #   40: 1/62        = 0.016129
    result = rrf([[10, 20, 30], [20, 40, 10]], weights=[2.0, 1.0], k=60)

    assert [chunk_id for chunk_id, _ in result] == [10, 20, 30, 40]
