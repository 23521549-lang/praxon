"""Test cho module do F1 text-to-LTL (task 6.5).

Khong annotation o ham test (quy uoc repo). Ten test tieng Viet, mo ta
hanh vi. So F1 cua bai bao Grohs et al. 2023 dung lam dap an doi chieu:
sheet Summary, dong "Examples provided, Try 1".
"""

from __future__ import annotations

import pytest

from praxon_core.eval.text_to_ltl import (
    TEMPLATES,
    TEXT_TO_LTL_SCHEMA,
    build_prompt,
    f1_for_template,
    f1_per_template,
    overall_f1,
    parse_model_output,
)


def _danh_sach_theo_so_dem(
    tp: int, fp: int, fn: int
) -> tuple[list[frozenset[str]], list[tuple[str, ...]]]:
    """Xay danh sach (du doan, dap an) chi cho mot mau, dat dung TP/FP/FN.

    Moi cau chi mang mau dang xet (hoac rong). Dung de doi chieu cong thuc
    F1 voi so dem da biet truoc.
    """
    predicted: list[frozenset[str]] = []
    gold: list[tuple[str, ...]] = []
    for _ in range(tp):
        predicted.append(frozenset({"precedence"}))
        gold.append(("precedence",))
    for _ in range(fp):
        predicted.append(frozenset({"precedence"}))
        gold.append(())
    for _ in range(fn):
        predicted.append(frozenset())
        gold.append(("precedence",))
    return predicted, gold


def test_f1_theo_mau_khop_so_bao_cao_grohs():
    """F1 theo tung mau tinh tu so dem TP/FP/FN cua bai bao phai khop Summary.

    So dem suy tu Precision/Recall trong sheet Summary (dong Try 1):
    precedence TP 27/28 du doan, 27/51 dap an; response 55/81, 55/57;
    succession 3/3, 3/3; init 9/9, 9/11; end 1/1, 1/6.
    """
    cases = [
        ("precedence", 27, 1, 24, 0.6835443037974683),
        ("response", 55, 26, 2, 0.7971014492753624),
        ("succession", 3, 0, 0, 1.0),
        ("init", 9, 0, 2, 0.9),
        ("end", 1, 0, 5, 0.2857142857142857),
    ]
    for template, tp, fp, fn, expected in cases:
        predicted, gold = _danh_sach_theo_so_dem(tp, fp, fn)
        # _danh_sach dung mau "precedence" lam mau cho; doi ten khi can.
        if template != "precedence":
            predicted = [
                frozenset({template if x == "precedence" else x for x in s}) for s in predicted
            ]
            gold = [tuple(template if x == "precedence" else x for x in s) for s in gold]
        score = f1_for_template(predicted, gold, template)
        assert score.tp == tp
        assert score.fp == fp
        assert score.fn == fn
        assert score.f1 == pytest.approx(expected)
        assert score.precision == pytest.approx(tp / (tp + fp))
        assert score.recall == pytest.approx(tp / (tp + fn))


def test_f1_tinh_tay_don_gian():
    """Vi du nho tinh tay: 2 TP, 1 FP, 1 FN thi P=2/3, R=2/3, F1=2/3."""
    predicted = [frozenset({"response"}), frozenset({"response"}), frozenset({"response"})]
    gold = [("response",), ("response",), ()]
    score = f1_for_template(predicted, gold, "response")
    assert score.tp == 2
    assert score.fp == 1
    assert score.fn == 0
    # Cau 3: du doan response, dap an rong -> FP; khong co FN o day.
    assert score.precision == pytest.approx(2 / 3)
    assert score.recall == pytest.approx(1.0)
    assert score.f1 == pytest.approx(0.8)


def test_f1_nhan_lap_dem_theo_so_lan_xuat_hien():
    """Mot cau co cung mau o 2 cot nhan thi dem 2 lan (theo bai bao).

    Cau 1 co nhan ("precedence", "precedence") va mo hinh du doan
    precedence -> TP 2 (moi nhan mot TP). Cau 2 co nhan
    ("precedence", "response") ma mo hinh chi du doan precedence ->
    precedence TP 1, response FN 1. Tong: precedence TP 3, response FN 1.
    """
    predicted = [frozenset({"precedence"}), frozenset({"precedence"})]
    gold = [("precedence", "precedence"), ("precedence", "response")]
    score = f1_for_template(predicted, gold, "precedence")
    assert score.tp == 3
    assert score.fp == 0
    assert score.fn == 0
    assert score.recall == pytest.approx(1.0)
    score_response = f1_for_template(predicted, gold, "response")
    assert score_response.tp == 0
    assert score_response.fn == 1
    assert score_response.f1 == 0.0


def test_f1_mau_so_rong_bang_0():
    """Khong co du doan lan dap an cho mot mau thi F1 cua mau do la 0."""
    predicted = [frozenset({"response"}), frozenset()]
    gold = [("response",), ()]
    score = f1_for_template(predicted, gold, "init")
    assert score.tp == 0
    assert score.fp == 0
    assert score.fn == 0
    assert score.precision == 0.0
    assert score.recall == 0.0
    assert score.f1 == 0.0


def test_f1_per_template_tra_du_5_mau_theo_thu_tu():
    """f1_per_template tra dict du 5 mau, dung thu tu TEMPLATES."""
    predicted = [frozenset({"precedence"}), frozenset({"response"})]
    gold = [("precedence",), ("precedence",)]
    result = f1_per_template(predicted, gold)
    assert list(result) == list(TEMPLATES)
    assert result["precedence"].f1 == pytest.approx(2 / 3)
    assert result["response"].f1 == pytest.approx(0.0)
    assert result["succession"].f1 == 0.0


def test_overall_f1_la_micro_gop_ca_5_mau():
    """Overall la micro-F1: gop TP/FP/FN cua ca 5 mau roi tinh.

    Vi du tinh tay: precedence TP 1; response TP 1, FP 1, FN 1.
    Tong: TP 2, FP 1, FN 1 -> P 2/3, R 2/3, F1 2/3.
    """
    predicted = [
        frozenset({"precedence"}),
        frozenset({"response"}),
        frozenset({"response"}),
        frozenset(),
    ]
    gold = [
        ("precedence",),
        ("response",),
        (),
        ("response",),
    ]
    score = overall_f1(predicted, gold)
    assert score.tp == 2
    assert score.fp == 1
    assert score.fn == 1
    assert score.precision == pytest.approx(2 / 3)
    assert score.recall == pytest.approx(2 / 3)
    assert score.f1 == pytest.approx(2 / 3)


def test_parse_model_output_json_hop_le():
    """Text JSON dung schema thi lay dung mang templates, loai ten la."""
    text = '{"templates": ["precedence", "response", "khong_co_mau_nay"]}'
    assert parse_model_output(text) == frozenset({"precedence", "response"})


def test_parse_model_output_json_rong():
    """JSON co mang rong thi tra tap rong."""
    assert parse_model_output('{"templates": []}') == frozenset()


def test_parse_model_output_text_thuong_khong_phai_json():
    """Text thuong (khong phai JSON) thi khop ten mau theo ranh gioi tu."""
    text = "The rule is a Precedence constraint, not a response."
    assert parse_model_output(text) == frozenset({"precedence", "response"})


def test_parse_model_output_khong_chua_mau_nao():
    """Text khong chua ten mau nao thi tra tap rong, khong nem loi."""
    assert parse_model_output("I cannot determine the rule.") == frozenset()
    assert parse_model_output("") == frozenset()
    assert parse_model_output("not a json {") == frozenset()


def test_parse_model_output_json_thieu_truong_templates():
    """JSON khong co truong templates thi roi ve khop text (tim ten mau)."""
    assert parse_model_output('{"answer": "precedence"}') == frozenset({"precedence"})


def test_build_prompt_chua_cau_vi_du_va_5_mau():
    """Prompt chua cau can do, cau vi du 1-shot, va ca 5 ten mau."""
    sentence = "A claim should be created, before it can be approved."
    prompt = build_prompt(sentence)
    assert sentence in prompt
    assert "A payment must be made before the order is shipped." in prompt
    for template in TEMPLATES:
        assert template in prompt
    assert '"templates"' in prompt
    # Cau vi du khong trung cau can do (vi du tu viet, ngoai bo 104 cau).
    assert prompt.count(sentence) == 1


def test_schema_chi_cho_5_mau():
    """Schema ep dinh dang chi cho phep 5 mau trong TEMPLATES."""
    assert TEXT_TO_LTL_SCHEMA["type"] == "object"
    assert TEXT_TO_LTL_SCHEMA["required"] == ["templates"]
    items = TEXT_TO_LTL_SCHEMA["properties"]["templates"]["items"]
    assert items["enum"] == list(TEMPLATES)
