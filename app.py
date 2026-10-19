import json
import os

from flask import Flask, abort, render_template, request

app = Flask(__name__)

# Resolve paths relative to this file so the app works from any working directory.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
IMG_DIR = os.path.join(BASE_DIR, "static", "img")


def load_fish():
    """อ่านไฟล์ .json ทุกไฟล์ใน data/ แล้วคืนเป็นรายการปลา (list ของ dict)"""
    fish_list = []
    for filename in sorted(os.listdir(DATA_DIR)):
        if not filename.endswith(".json"):
            continue
        path = os.path.join(DATA_DIR, filename)
        try:
            with open(path, encoding="utf-8") as f:
                fish = json.load(f)
        except json.JSONDecodeError as e:
            print(f"[Find Fish] ข้ามไฟล์ {filename} เพราะอ่านไม่ได้: {e}")
            continue

        image_name = fish.get("image", "")
        fish["has_image"] = bool(image_name) and os.path.exists(
            os.path.join(IMG_DIR, image_name)
        )
        fish_list.append(fish)
    return fish_list


def pond_list(fish):
    """คืนค่า pond เป็น list เสมอ — รองรับทั้งกรณีในไฟล์เป็น string เดี่ยว หรือ list"""
    p = fish.get("pond") or []
    if isinstance(p, str):
        return [p] if p else []
    return p


def compare_value(fish, key, fallback="ยังไม่มีข้อมูล"):
    """คืนค่าที่เหมาะแสดงในตารางเปรียบเทียบ โดยไม่แต่งเติมข้อมูลที่ไม่มี"""
    value = fish.get(key)
    if value is None or value == "" or value == []:
        return fallback
    if isinstance(value, list):
        return " · ".join(str(item) for item in value if item) or fallback
    return str(value)


def comparison_data(fishes):
    """เตรียมแถวเปรียบเทียบและทำเครื่องหมายค่าตัวเลขที่เด่นที่สุด"""
    groups = [
        ("ข้อมูลทั่วไป", [
            ("name_th", "ชื่อไทย"),
            ("name_sci", "ชื่อวิทยาศาสตร์"),
            ("identify", "ลักษณะเด่น"),
            ("habitat", "ถิ่นที่พบ/รายละเอียดทั่วไป"),
        ]),
        ("การเลี้ยง", [
            ("duration", "ระยะเวลาเลี้ยงจนจับขาย"),
            ("harvest_detail", "ขนาด/รายละเอียดจับขาย"),
            ("food", "อาหารที่กิน"),
        ]),
        ("สภาพแวดล้อม", [
            ("temperature", "อุณหภูมิน้ำ"),
            ("ph", "pH"),
            ("O2", "ออกซิเจนละลายน้ำ"),
            ("diseases", "โรคที่พบบ่อย"),
            ("pond", "รูปแบบบ่อที่เลี้ยงได้"),
        ]),
        ("เศรษฐกิจ", [
            ("total_cost", "รายละเอียดการคิดต้นทุนการเลี้ยงโดยประมาณ"),
            ("cost", "ต้นทุนการเลี้ยงโดยประมาณ(ราคา/100 ตัว)"),
            ("price", "ราคาขายต่อกิโลกรัม"),
            ("market", "ตลาดหลัก"),
        ]),
    ]

    def value_for(fish, key):
        if key == "name_th":
            return compare_value(fish, "name_th")
        if key == "name_sci":
            return compare_value(fish, "name_sci")
        if key == "identify":
            return compare_value(fish, "identify")
        if key == "pond":
            return compare_value(fish, "pond")
        if key == "duration":
            duration = fish.get("duration") or {}
            minimum = duration.get("months_min")
            maximum = duration.get("months_max")
            if (
                isinstance(minimum, (int, float))
                and not isinstance(minimum, bool)
                and minimum > 0
                and isinstance(maximum, (int, float))
                and not isinstance(maximum, bool)
                and maximum > 0
            ):
                return f"{minimum:g}–{maximum:g} เดือน"
            return "ยังไม่มีข้อมูล"
        if key == "harvest_detail":
            return compare_value(fish.get("duration") or {}, "detail")
        if key == "food":
            food = fish.get("food") or {}
            parts = [food.get("type"), food.get("detail")]
            return " — ".join(part for part in parts if part) or "ยังไม่มีข้อมูล"
        if key == "diseases":
            diseases = fish.get("diseases") or []
            names = [
                disease.get("name")
                for disease in diseases
                if disease.get("name")
            ]
            return " · ".join(names) or "ยังไม่มีข้อมูล"
        if key in {"total_cost", "cost", "price", "market"}:
            economy = fish.get("economy") or []
            if isinstance(economy, list):
                economy = economy[0] if economy else {}
            return compare_value(economy, key)
        if key in {"temperature", "ph", "oxygen", "O2", "salinity"}:
            water = fish.get("water") or {}
            water_key = {
                "temperature": "temp",
                "ph": "ph",
                "oxygen": "oxygen",
                "O2": "O2",
                "salinity": "salinity",
            }[key]
            return compare_value(water, water_key)
        if key == "habitat":
            return compare_value(fish, "description")
        return compare_value(fish, key)

    sections = []
    metric_specs = {
        "duration": ("duration", "months_min", "min"),
        "price": (None, "price", "max"),
        "fcr": (None, "fcr", "min"),
    }
    for group_name, definitions in groups:
        rows = []
        for key, label in definitions:
            cells = [
                {"value": value_for(fish, key), "highlight": False}
                for fish in fishes
            ]
            if key in metric_specs:
                parent_key, value_key, direction = metric_specs[key]
                metric_values = []
                for index, fish in enumerate(fishes):
                    source = fish
                    if parent_key:
                        source = fish.get(parent_key) or {}
                    metric = source.get(value_key)
                    if (
                        isinstance(metric, (int, float))
                        and not isinstance(metric, bool)
                        and metric > 0
                    ):
                        metric_values.append((index, metric))

                if metric_values:
                    best_value = (
                        min(value for _, value in metric_values)
                        if direction == "min"
                        else max(value for _, value in metric_values)
                    )
                    for index, value in metric_values:
                        cells[index]["highlight"] = value == best_value

            rows.append(
                {
                    "label": label,
                    "cells": cells,
                    "identical": len({cell["value"] for cell in cells}) <= 1,
                }
            )
        sections.append({"name": group_name, "rows": rows})
    return sections


@app.route("/")
def landing():
    """หน้าแนะนำเว็บไซต์ก่อนเข้าสู่รายการปลา"""
    return render_template("landing.html")


@app.route("/index")
def index():
    """หน้ารายการปลาทุกตัว พร้อมตัวเลือกเรียงลำดับ"""
    selected_sort = request.args.get("sort", "name")
    if selected_sort not in {"name", "fastest", "slowest"}:
        selected_sort = "name"

    fish_list = load_fish()
    name_key = lambda fish: (fish.get("name_th") or "").casefold()

    if selected_sort == "name":
        fish_list.sort(key=name_key)
    else:
        def growth_months(fish):
            duration = fish.get("duration") or {}
            months = duration.get("months_min")
            if isinstance(months, (int, float)) and not isinstance(months, bool) and months > 0:
                return months
            return None

        known_duration = [fish for fish in fish_list if growth_months(fish) is not None]
        missing_duration = [fish for fish in fish_list if growth_months(fish) is None]
        known_duration.sort(
            key=lambda fish: (
                growth_months(fish) if selected_sort == "fastest" else -growth_months(fish),
                name_key(fish),
            )
        )
        missing_duration.sort(key=name_key)
        fish_list = known_duration + missing_duration

    return render_template(
        "index.html", fish_list=fish_list, selected_sort=selected_sort
    )


@app.route("/filter")
def filterpage():
    """หน้าเลือกกรองปลา"""
    fishes = load_fish()
    selected_food = (request.args.get("food") or "").strip()
    selected_pond = (request.args.get("pond") or "").strip()

    if selected_food:
        fishes = [fish for fish in fishes if (fish.get("food") or {}).get("type") == selected_food]
    if selected_pond:
        fishes = [fish for fish in fishes if selected_pond in pond_list(fish)]

    food_types = sorted(
        {
            (fish.get("food") or {}).get("type")
            for fish in load_fish()
            if (fish.get("food") or {}).get("type")
        }
    )
    pond_types = sorted({pond for fish in load_fish() for pond in pond_list(fish)})

    return render_template(
        "filter.html",
        fishes=fishes,
        total=len(load_fish()),
        food_types=food_types,
        pond_types=pond_types,
        selected_food=selected_food,
        selected_pond=selected_pond,
    )


@app.route("/diseases")
def disease_list():
    """หน้ารวมโรคจากปลาทุกชนิด พร้อมข้อมูลปลาเจ้าของโรค"""
    diseases = []
    for fish in load_fish():
        for disease in fish.get("diseases") or []:
            if not disease.get("name"):
                continue
            diseases.append(
                {
                    "name": disease["name"],
                    "symptom": disease.get("symptom") or "",
                    "note": disease.get("note") or "",
                    "fish_id": fish.get("id"),
                    "fish_name": fish.get("name_th") or fish.get("id"),
                }
            )

    return render_template("diseases.html", diseases=diseases)


@app.route("/compare")
def compare():
    """เลือกปลา 2–4 ชนิดเพื่อเปรียบเทียบข้อมูลที่มีอยู่"""
    all_fish = load_fish()
    fish_by_id = {fish.get("id"): fish for fish in all_fish if fish.get("id")}
    requested_ids = []
    for value in request.args.getlist("fish"):
        requested_ids.extend(part.strip() for part in value.split(",") if part.strip())
    selected_ids = []
    for fish_id in requested_ids:
        if fish_id in fish_by_id and fish_id not in selected_ids:
            selected_ids.append(fish_id)
    selected_ids = selected_ids[:4]
    selected_fish = [fish_by_id[fish_id] for fish_id in selected_ids]

    if len(selected_fish) < 2 or request.args.get("select") == "1":
        return render_template(
            "compare_select.html",
            fish_list=all_fish,
            selected_ids=selected_ids,
        )

    shared_ponds = set(pond_list(selected_fish[0]))
    for fish in selected_fish[1:]:
        shared_ponds.intersection_update(pond_list(fish))

    recommendations = []
    if shared_ponds:
        recommendations.append(
            "รูปแบบบ่อที่ข้อมูลระบุว่ารองรับร่วมกัน: "
            + " · ".join(sorted(shared_ponds))
            + " ควรพิจารณาความเหมาะสมของบ่อจริงและการเลี้ยงร่วมเพิ่มเติม"
        )
    else:
        recommendations.append(
            "ข้อมูลปัจจุบันไม่พบรูปแบบบ่อที่ระบุว่ารองรับร่วมกันทุกชนิด "
            "ควรตรวจสอบระบบเลี้ยงของแต่ละชนิดก่อนตัดสินใจ"
        )

    food_types = [(fish.get("food") or {}).get("type") for fish in selected_fish]
    if all(food_types) and len(set(food_types)) == 1:
        recommendations.append(
            f"ปลาในชุดนี้ระบุประเภทอาหารเหมือนกัน ({food_types[0]}) "
            "แต่รายละเอียดสูตรและปริมาณอาหารอาจต่างกัน"
        )
    elif any(food_types):
        recommendations.append(
            "ประเภทอาหารที่ระบุแตกต่างกันหรือมีข้อมูลไม่ครบ "
            "ควรเตรียมอาหารตามความต้องการของปลาแต่ละชนิด"
        )

    known_durations = [
        (fish, (fish.get("duration") or {}).get("months_min"))
        for fish in selected_fish
    ]
    known_durations = [
        (fish, months)
        for fish, months in known_durations
        if isinstance(months, (int, float))
        and not isinstance(months, bool)
        and months > 0
    ]
    if known_durations:
        shortest_months = min(months for _, months in known_durations)
        shortest_fish = [
            fish.get("name_th")
            for fish, months in known_durations
            if months == shortest_months
        ]
        recommendations.append(
            "ระยะเลี้ยงขั้นต่ำที่มีข้อมูลสั้นที่สุดในชุดนี้: "
            + " และ ".join(shortest_fish)
            + f" ({shortest_months:g} เดือนขึ้นไปตามข้อมูลที่มี) "
            "ระยะเวลาสั้นกว่าไม่ได้ยืนยันว่าคุ้มทุนหรือเหมาะกับทุกฟาร์ม"
        )

    return render_template(
        "compare_results.html",
        fishes=selected_fish,
        sections=comparison_data(selected_fish),
        recommendations=recommendations,
    )


@app.route("/fish/<fish_id>")
def fishdetail(fish_id):
    """หน้ารายละเอียดปลา 1 ตัว เช่น /fish/nil"""
    for fish in load_fish():
        if fish.get("id") == fish_id:
            return render_template("fish.html", fish=fish)
    abort(404)


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")