# version: 1.0
import machine_review_correction_runtime as runtime


def test_people_comparison_ignores_order_and_letter_case():
    assert runtime._same_value(["marek", "dawid"], ["Dawid", "Marek"])
    assert not runtime._same_value(["marek", "dawid"], ["marek"])
