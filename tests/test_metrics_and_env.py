from evals.env import StoreEnv, load_store
from evals.metrics import cohen_kappa, pass_at_k, pass_hat_k, wilson_interval


def test_pass_at_k_and_pass_hat_k():
    # 3 of 4 trials pass
    assert pass_at_k(4, 3, 1) == 0.75
    assert pass_hat_k(4, 3, 1) == 0.75
    assert pass_at_k(4, 3, 2) == 1.0          # with 2 tries you can't miss both, only 1 failure exists
    assert abs(pass_hat_k(4, 3, 2) - 0.5) < 1e-9   # C(3,2)/C(4,2) = 3/6
    assert pass_hat_k(4, 3, 4) == 0.0
    assert pass_at_k(4, 0, 4) == 0.0
    assert pass_hat_k(5, 5, 5) == 1.0


def test_reliability_falls_off_fast():
    # The classic illustration: 75% per try, all 3 tries succeed about 42% of the time.
    assert abs(0.75 ** 3 - 0.42) < 0.01


def test_wilson_interval():
    lo, hi = wilson_interval(35, 50)
    assert 0.55 < lo < 0.58 and 0.80 < hi < 0.83
    assert wilson_interval(0, 0) == (0.0, 0.0)


def test_kappa():
    assert cohen_kappa(10, 0, 0, 10) == 1.0
    assert abs(cohen_kappa(5, 5, 5, 5)) < 1e-9   # coin flip agreement


def test_trials_are_isolated():
    a, b = StoreEnv(), StoreEnv()
    a.call_tool("cancel_order", {"order_id": "R-1050"})
    a.call_tool("issue_refund", {"order_id": "R-1042", "item_ids": ["I-1"], "reason": "x"})
    assert b.state["orders"]["R-1050"]["status"] == "processing"
    assert b.state["refunds"] == []
    assert load_store()["refunds"] == []


def test_initial_state_override():
    env = StoreEnv({"refunds": [{"refund_id": "RF-1", "order_id": "R-1042", "item_ids": ["I-2"], "amount": 39.0, "reason": "x"}]})
    out, err = env.call_tool("issue_refund", {"order_id": "R-1042", "item_ids": ["I-2"], "reason": "again"})
    assert err and "already refunded" in out


def test_backend_does_not_enforce_policy():
    # The mock backend lets bad actions through on purpose. The agent is the policy layer.
    env = StoreEnv()
    _, err = env.call_tool("cancel_order", {"order_id": "R-1051"})  # shipped
    assert not err
    _, err = env.call_tool("issue_refund", {"order_id": "R-1061", "item_ids": ["I-1"], "reason": "x"})  # final sale
    assert not err
