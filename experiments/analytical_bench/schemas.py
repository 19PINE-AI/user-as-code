"""Record schemas for the 10 analytical benchmark types.

Each type defines:
- the fields that show up in records
- a generator function (seed, n) -> list[dict]
- a list of question templates (each: id, text, gold_fn(records) -> answer, answer_kind)

Answer kinds: "int", "float", "string", "set", "list" (used by the scorer).
"""
from __future__ import annotations

import random
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from typing import Any, Callable

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rng(seed: int) -> random.Random:
    return random.Random(seed)


def _date_in(rng: random.Random, start: date, end: date) -> date:
    delta_days = (end - start).days
    return start + timedelta(days=rng.randint(0, max(delta_days, 0)))


def _round(x: float, places: int = 2) -> float:
    return round(x, places)


# ---------------------------------------------------------------------------
# Schema 1: Trips
# ---------------------------------------------------------------------------

DESTINATIONS = [
    ("Tokyo", "Japan", "Asia"),
    ("Paris", "France", "Europe"),
    ("New York", "USA", "Americas"),
    ("Sydney", "Australia", "Oceania"),
    ("Cape Town", "South Africa", "Africa"),
    ("Berlin", "Germany", "Europe"),
    ("Rio de Janeiro", "Brazil", "Americas"),
    ("Bangkok", "Thailand", "Asia"),
    ("Toronto", "Canada", "Americas"),
    ("Reykjavik", "Iceland", "Europe"),
    ("Singapore", "Singapore", "Asia"),
    ("Cairo", "Egypt", "Africa"),
    ("Buenos Aires", "Argentina", "Americas"),
    ("Lisbon", "Portugal", "Europe"),
    ("Seoul", "South Korea", "Asia"),
]
TRIP_PURPOSES = ["business", "personal", "family", "conference", "vacation"]
TRIP_TRANSPORT = ["plane", "train", "car", "bus"]


def gen_trips(seed: int, n: int) -> list[dict]:
    rng = _rng(seed)
    out = []
    start = date(2022, 1, 1)
    end = date(2025, 12, 31)
    for i in range(n):
        dest = rng.choice(DESTINATIONS)
        d = _date_in(rng, start, end)
        duration = rng.randint(1, 21)
        out.append({
            "id": i,
            "date": d.isoformat(),
            "destination": dest[0],
            "country": dest[1],
            "region": dest[2],
            "duration_days": duration,
            "purpose": rng.choice(TRIP_PURPOSES),
            "cost_usd": _round(rng.uniform(150, 5000)),
            "transportation": rng.choice(TRIP_TRANSPORT),
        })
    out.sort(key=lambda r: r["date"])
    return out


def trip_questions(records: list[dict]) -> list[dict]:
    yr_24 = [r for r in records if r["date"].startswith("2024")]
    asia = [r for r in records if r["region"] == "Asia"]
    biz = [r for r in records if r["purpose"] == "business"]
    by_country = Counter(r["country"] for r in records)
    by_purpose = Counter(r["purpose"] for r in records)
    total_cost_24 = sum(r["cost_usd"] for r in yr_24)
    avg_duration_business = (
        sum(r["duration_days"] for r in biz) / len(biz) if biz else 0
    )
    long_trips = [r for r in records if r["duration_days"] >= 14]
    cost_business_2024 = sum(
        r["cost_usd"] for r in yr_24 if r["purpose"] == "business"
    )
    longest = max(records, key=lambda r: r["duration_days"]) if records else None
    most_visited_country = by_country.most_common(1)[0][0] if by_country else None
    yearly_counts = Counter(r["date"][:4] for r in records)
    trend_2023_to_2024 = "increase" if yearly_counts["2024"] > yearly_counts["2023"] else (
        "decrease" if yearly_counts["2024"] < yearly_counts["2023"] else "same"
    )
    return [
        {"id": "trips_count_2024", "kind": "int",
         "q": "How many trips did I take in 2024?",
         "a": len(yr_24)},
        {"id": "trips_sum_cost_2024", "kind": "float",
         "q": "What was my total trip cost in USD in 2024?",
         "a": _round(total_cost_24)},
        {"id": "trips_avg_business_duration", "kind": "float",
         "q": "What was the average duration in days of my business trips?",
         "a": _round(avg_duration_business)},
        {"id": "trips_groupby_purpose", "kind": "set",
         "q": "List the trip purposes that account for at least 25% of all my trips.",
         "a": sorted({p for p, c in by_purpose.items() if c / len(records) >= 0.25})},
        {"id": "trips_window_jan_jun_2024", "kind": "int",
         "q": "How many trips did I take between 2024-01-01 and 2024-06-30 inclusive?",
         "a": sum(1 for r in records if "2024-01-01" <= r["date"] <= "2024-06-30")},
        {"id": "trips_multi_asia_business", "kind": "int",
         "q": "How many of my trips were business trips to Asia?",
         "a": sum(1 for r in asia if r["purpose"] == "business")},
        {"id": "trips_topk_country", "kind": "string",
         "q": "Which country did I visit the most? (single name)",
         "a": most_visited_country},
        {"id": "trips_min_max_longest", "kind": "string",
         "q": "What was the destination of my longest trip? If multiple are tied, give the earliest by date.",
         "a": longest["destination"] if longest else ""},
        {"id": "trips_long_count", "kind": "int",
         "q": "How many of my trips lasted 14 days or longer?",
         "a": len(long_trips)},
        {"id": "trips_trend_yoy", "kind": "string",
         "q": "Did my trip count increase, decrease, or stay the same from 2023 to 2024? (one word)",
         "a": trend_2023_to_2024},
    ]


# ---------------------------------------------------------------------------
# Schema 2: Contacts
# ---------------------------------------------------------------------------

FIRST_NAMES = ["Alex", "Jamie", "Casey", "Pat", "Robin", "Riley", "Quinn",
               "Morgan", "Sasha", "Drew", "Sam", "Taylor", "Jordan", "Cameron",
               "Avery", "Skyler", "Reese", "Parker", "Hayden", "Logan"]
LAST_NAMES = ["Chen", "Patel", "Kim", "Nguyen", "Garcia", "Smith", "Johnson",
              "Williams", "Brown", "Davis", "Lee", "Martinez", "Anderson",
              "Wilson", "Thompson"]
RELATION_TYPES = ["friend", "colleague", "family", "acquaintance", "mentor"]
MET_CONTEXTS = ["undergrad", "grad-school", "work", "conference", "online", "neighborhood", "hobby-group"]


def gen_contacts(seed: int, n: int) -> list[dict]:
    rng = _rng(seed)
    out = []
    today = date(2025, 6, 1)
    used_names: set[str] = set()
    suffix = 0
    for i in range(n):
        # Try a few random first/last combos; if all collide, fall back to a
        # numbered suffix so we never spin in a tight loop on large N.
        name = None
        for _ in range(10):
            candidate = f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"
            if candidate not in used_names:
                name = candidate
                break
        if name is None:
            suffix += 1
            name = f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}-{suffix}"
        used_names.add(name)
        rel = rng.choice(RELATION_TYPES)
        met_ctx = rng.choice(MET_CONTEXTS)
        met = _date_in(rng, date(2010, 1, 1), today)
        last_contact = _date_in(rng, met, today)
        out.append({
            "id": i,
            "name": name,
            "relationship": rel,
            "met_date": met.isoformat(),
            "met_context": met_ctx,
            "last_contact_date": last_contact.isoformat(),
        })
    out.sort(key=lambda r: r["met_date"])
    return out


def contact_questions(records: list[dict]) -> list[dict]:
    today = date(2025, 6, 1)
    a_year_ago = today - timedelta(days=365)
    contacted_last_year = [r for r in records if r["last_contact_date"] >= a_year_ago.isoformat()]
    undergrad = [r for r in records if r["met_context"] == "undergrad"]
    by_rel = Counter(r["relationship"] for r in records)
    by_ctx = Counter(r["met_context"] for r in records)
    friends = [r for r in records if r["relationship"] == "friend"]
    work_friends = [r for r in records if r["met_context"] == "work" and r["relationship"] == "friend"]
    long_known = [r for r in records if r["met_date"] < (today - timedelta(days=365 * 5)).isoformat()]
    most_common_ctx = by_ctx.most_common(1)[0][0] if by_ctx else None
    relationships_with_ge_25_pct = sorted({r for r, c in by_rel.items() if c / len(records) >= 0.25})
    earliest = min(records, key=lambda r: r["met_date"]) if records else None
    yearly_met = Counter(r["met_date"][:4] for r in records)
    sorted_years = sorted(yearly_met)
    trend_first_to_last = "increase" if sorted_years and yearly_met[sorted_years[-1]] > yearly_met[sorted_years[0]] else (
        "decrease" if sorted_years and yearly_met[sorted_years[-1]] < yearly_met[sorted_years[0]] else "same"
    )
    return [
        {"id": "contacts_count_year", "kind": "int",
         "q": f"How many contacts have I been in touch with in the last 365 days (last contact on or after {a_year_ago.isoformat()})?",
         "a": len(contacted_last_year)},
        {"id": "contacts_count_undergrad", "kind": "int",
         "q": "How many of my contacts did I first meet during undergrad?",
         "a": len(undergrad)},
        {"id": "contacts_avg_friends", "kind": "float",
         "q": "What fraction of my contacts are classified as friends? Give a decimal between 0 and 1, rounded to 2 places.",
         "a": _round(len(friends) / len(records))},
        {"id": "contacts_groupby_topctx", "kind": "string",
         "q": "What is the single most common context in which I met my contacts?",
         "a": most_common_ctx},
        {"id": "contacts_window_2020", "kind": "int",
         "q": "How many contacts did I first meet in calendar year 2020?",
         "a": sum(1 for r in records if r["met_date"].startswith("2020"))},
        {"id": "contacts_multi_work_friends", "kind": "int",
         "q": "How many contacts are friends I met at work?",
         "a": len(work_friends)},
        {"id": "contacts_topk_relationships", "kind": "set",
         "q": "List the relationship types that account for at least 25% of all my contacts.",
         "a": relationships_with_ge_25_pct},
        {"id": "contacts_earliest", "kind": "string",
         "q": "What is the name of the contact I have known the longest (earliest met_date)?",
         "a": earliest["name"] if earliest else ""},
        {"id": "contacts_long_known", "kind": "int",
         "q": "How many contacts have I known for more than 5 years (met_date more than 5 years before 2025-06-01)?",
         "a": len(long_known)},
        {"id": "contacts_trend", "kind": "string",
         "q": "Comparing the year I met the most recent contact vs the year I met the earliest, did I meet more, fewer, or the same number? (one word: increase/decrease/same)",
         "a": trend_first_to_last},
    ]


# ---------------------------------------------------------------------------
# Schema 3: Meals
# ---------------------------------------------------------------------------

MEAL_TYPES = ["breakfast", "lunch", "dinner", "snack"]
CUISINES = ["italian", "japanese", "mexican", "indian", "american", "thai",
            "french", "chinese", "mediterranean", "korean"]
RESTAURANTS = ["The Garden", "Pasta Place", "Sushi Bar", "Taco Truck",
               "Curry House", "Burger Joint", "Bistro 47", "Wok Express",
               "Olive Branch", "Seoul Kitchen", "Cafe Lumina", "Spice Route"]


def gen_meals(seed: int, n: int) -> list[dict]:
    rng = _rng(seed)
    out = []
    start = date(2024, 1, 1)
    end = date(2024, 12, 31)
    for i in range(n):
        d = _date_in(rng, start, end)
        out.append({
            "id": i,
            "date": d.isoformat(),
            "meal_type": rng.choice(MEAL_TYPES),
            "cuisine": rng.choice(CUISINES),
            "restaurant": rng.choice(RESTAURANTS),
            "dined_in": rng.random() < 0.6,
            "cost_usd": _round(rng.uniform(5, 80)),
            "calories": rng.randint(150, 1500),
        })
    out.sort(key=lambda r: r["date"])
    return out


def meal_questions(records: list[dict]) -> list[dict]:
    breakfasts = [r for r in records if r["meal_type"] == "breakfast"]
    italian = [r for r in records if r["cuisine"] == "italian"]
    by_cuisine = Counter(r["cuisine"] for r in records)
    by_meal = Counter(r["meal_type"] for r in records)
    summer = [r for r in records if "2024-06-01" <= r["date"] <= "2024-08-31"]
    high_cal = [r for r in records if r["calories"] >= 1000]
    dined_in_dinner = [r for r in records if r["dined_in"] and r["meal_type"] == "dinner"]
    total_cost = sum(r["cost_usd"] for r in records)
    avg_cost = total_cost / len(records) if records else 0
    top_cuisine = by_cuisine.most_common(1)[0][0] if by_cuisine else None
    cuisines_ge_15 = sorted({c for c, n in by_cuisine.items() if c == c and n >= 0.15 * len(records)})
    h1 = [r for r in records if "2024-01-01" <= r["date"] <= "2024-06-30"]
    h2 = [r for r in records if "2024-07-01" <= r["date"] <= "2024-12-31"]
    cost_trend = "increase" if sum(r["cost_usd"] for r in h2) > sum(r["cost_usd"] for r in h1) else (
        "decrease" if sum(r["cost_usd"] for r in h2) < sum(r["cost_usd"] for r in h1) else "same"
    )
    return [
        {"id": "meals_count_breakfast", "kind": "int",
         "q": "How many breakfasts did I eat in 2024?",
         "a": len(breakfasts)},
        {"id": "meals_sum_total_cost", "kind": "float",
         "q": "What was my total spending on meals in USD in 2024?",
         "a": _round(total_cost)},
        {"id": "meals_avg_cost", "kind": "float",
         "q": "What was the average cost in USD of my meals in 2024? Round to 2 decimals.",
         "a": _round(avg_cost)},
        {"id": "meals_groupby_cuisines_15pct", "kind": "set",
         "q": "List the cuisines that account for at least 15% of all my meals.",
         "a": cuisines_ge_15},
        {"id": "meals_window_summer", "kind": "int",
         "q": "How many meals did I eat between 2024-06-01 and 2024-08-31 inclusive?",
         "a": len(summer)},
        {"id": "meals_multi_dined_dinner", "kind": "int",
         "q": "How many dinners did I eat that were dined-in (not takeout)?",
         "a": len(dined_in_dinner)},
        {"id": "meals_topk_cuisine", "kind": "string",
         "q": "What single cuisine appears most frequently in my meals?",
         "a": top_cuisine},
        {"id": "meals_max_calories", "kind": "int",
         "q": "How many meals had 1000 or more calories?",
         "a": len(high_cal)},
        {"id": "meals_italian_count", "kind": "int",
         "q": "How many italian-cuisine meals did I have?",
         "a": len(italian)},
        {"id": "meals_trend_h1_h2", "kind": "string",
         "q": "Did my total meal spending increase, decrease, or stay the same from H1 (Jan-Jun) to H2 (Jul-Dec) of 2024? (one word)",
         "a": cost_trend},
    ]


# ---------------------------------------------------------------------------
# Schema 4: Transactions
# ---------------------------------------------------------------------------

TX_CATEGORIES = ["groceries", "dining", "entertainment", "utilities",
                 "transportation", "healthcare", "shopping", "subscriptions",
                 "rent", "education"]
TX_VENDORS = ["BigMart", "QuickGas", "StreamCo", "PowerCorp", "InsureCo",
              "MetroTransit", "GadgetHub", "PetStore", "FitnessPlus", "CloudSub"]
TX_PAYMENTS = ["credit_card", "debit_card", "bank_transfer", "cash"]


def gen_transactions(seed: int, n: int) -> list[dict]:
    rng = _rng(seed)
    out = []
    start = date(2024, 1, 1)
    end = date(2024, 12, 31)
    for i in range(n):
        d = _date_in(rng, start, end)
        cat = rng.choice(TX_CATEGORIES)
        amount = rng.uniform(5, 800) if cat != "rent" else rng.uniform(800, 3000)
        out.append({
            "id": i,
            "date": d.isoformat(),
            "amount_usd": _round(amount),
            "category": cat,
            "vendor": rng.choice(TX_VENDORS),
            "payment_method": rng.choice(TX_PAYMENTS),
        })
    out.sort(key=lambda r: r["date"])
    return out


def transaction_questions(records: list[dict]) -> list[dict]:
    total = sum(r["amount_usd"] for r in records)
    groceries = [r for r in records if r["category"] == "groceries"]
    by_cat_total = defaultdict(float)
    for r in records:
        by_cat_total[r["category"]] += r["amount_usd"]
    top_cat = max(by_cat_total, key=by_cat_total.get) if by_cat_total else None
    avg_dining = (
        sum(r["amount_usd"] for r in records if r["category"] == "dining")
        / max(1, sum(1 for r in records if r["category"] == "dining"))
    )
    big = [r for r in records if r["amount_usd"] >= 500]
    q4 = [r for r in records if "2024-10-01" <= r["date"] <= "2024-12-31"]
    cc_subs = [r for r in records if r["payment_method"] == "credit_card" and r["category"] == "subscriptions"]
    by_payment = Counter(r["payment_method"] for r in records)
    payments_ge_25 = sorted({p for p, c in by_payment.items() if c / len(records) >= 0.25})
    q1_total = sum(r["amount_usd"] for r in records if "2024-01-01" <= r["date"] <= "2024-03-31")
    q4_total = sum(r["amount_usd"] for r in q4)
    trend = "increase" if q4_total > q1_total else ("decrease" if q4_total < q1_total else "same")
    return [
        {"id": "tx_count_groceries", "kind": "int",
         "q": "How many transactions are in the groceries category?",
         "a": len(groceries)},
        {"id": "tx_sum_total", "kind": "float",
         "q": "What was my total transaction amount in USD in 2024?",
         "a": _round(total)},
        {"id": "tx_avg_dining", "kind": "float",
         "q": "What was my average dining transaction amount in USD? Round to 2 decimals.",
         "a": _round(avg_dining)},
        {"id": "tx_groupby_top_category", "kind": "string",
         "q": "Which category did I spend the most money on in total? (single category name)",
         "a": top_cat},
        {"id": "tx_window_q4", "kind": "int",
         "q": "How many transactions did I make in Q4 2024 (2024-10-01 through 2024-12-31)?",
         "a": len(q4)},
        {"id": "tx_multi_cc_subs", "kind": "int",
         "q": "How many subscription-category transactions were paid by credit card?",
         "a": len(cc_subs)},
        {"id": "tx_topk_payment_methods", "kind": "set",
         "q": "List payment methods that account for at least 25% of all my transactions.",
         "a": payments_ge_25},
        {"id": "tx_big_count", "kind": "int",
         "q": "How many transactions were 500 USD or more?",
         "a": len(big)},
        {"id": "tx_q4_total", "kind": "float",
         "q": "What was my total spending in USD in Q4 2024 (2024-10-01 through 2024-12-31)?",
         "a": _round(q4_total)},
        {"id": "tx_trend_q1_q4", "kind": "string",
         "q": "Did my total spending increase, decrease, or stay the same from Q1 2024 to Q4 2024? (one word)",
         "a": trend},
    ]


# ---------------------------------------------------------------------------
# Schema 5: Sleep log
# ---------------------------------------------------------------------------

def gen_sleep(seed: int, n: int) -> list[dict]:
    rng = _rng(seed)
    out = []
    start = date(2024, 1, 1)
    for i in range(n):
        d = start + timedelta(days=i)
        bed_hour = rng.choice([22, 22, 23, 23, 23, 0, 0, 1])  # mostly late night
        bed_minute = rng.choice([0, 15, 30, 45])
        bedtime = f"{bed_hour:02d}:{bed_minute:02d}"
        sleep_hours = rng.uniform(5.5, 9.0)
        # compute wake time
        bed_dt = datetime.combine(d if bed_hour >= 12 else d + timedelta(days=1),
                                  datetime.strptime(bedtime, "%H:%M").time())
        wake_dt = bed_dt + timedelta(hours=sleep_hours)
        out.append({
            "id": i,
            "date": d.isoformat(),
            "bedtime": bedtime,
            "wake_time": wake_dt.strftime("%H:%M"),
            "duration_hours": _round(sleep_hours, 2),
            "quality": rng.choice(["good", "fair", "poor"]),
        })
    return out


def sleep_questions(records: list[dict]) -> list[dict]:
    early_wake = [r for r in records if r["wake_time"] < "07:00"]
    late_bed = [r for r in records if r["bedtime"] >= "23:00" or r["bedtime"] < "03:00"]
    poor = [r for r in records if r["quality"] == "poor"]
    avg_dur = sum(r["duration_hours"] for r in records) / len(records) if records else 0
    long_sleep = [r for r in records if r["duration_hours"] >= 8.0]
    by_quality = Counter(r["quality"] for r in records)
    top_quality = by_quality.most_common(1)[0][0] if by_quality else None
    q1 = [r for r in records if "2024-01-01" <= r["date"] <= "2024-03-31"]
    q2 = [r for r in records if "2024-04-01" <= r["date"] <= "2024-06-30"]
    q1_avg = sum(r["duration_hours"] for r in q1) / max(1, len(q1))
    q2_avg = sum(r["duration_hours"] for r in q2) / max(1, len(q2))
    trend = "increase" if q2_avg > q1_avg else ("decrease" if q2_avg < q1_avg else "same")
    poor_pct = len(poor) / len(records) if records else 0
    qualities_ge_25 = sorted({q for q, c in by_quality.items() if c / len(records) >= 0.25})
    longest = max(records, key=lambda r: r["duration_hours"]) if records else None
    return [
        {"id": "sleep_count_early_wake", "kind": "int",
         "q": "On how many nights did I wake up before 07:00?",
         "a": len(early_wake)},
        {"id": "sleep_avg_duration", "kind": "float",
         "q": "What was my average sleep duration in hours? Round to 2 decimals.",
         "a": _round(avg_dur)},
        {"id": "sleep_count_long", "kind": "int",
         "q": "On how many nights did I sleep at least 8.0 hours?",
         "a": len(long_sleep)},
        {"id": "sleep_groupby_top_quality", "kind": "string",
         "q": "What sleep quality value (good/fair/poor) appears most often?",
         "a": top_quality},
        {"id": "sleep_window_late_bed", "kind": "int",
         "q": "On how many nights was my bedtime at or after 23:00 (or between 00:00 and 02:59)?",
         "a": len(late_bed)},
        {"id": "sleep_multi_poor_short", "kind": "int",
         "q": "On how many nights was sleep quality poor AND duration less than 6.5 hours?",
         "a": sum(1 for r in records if r["quality"] == "poor" and r["duration_hours"] < 6.5)},
        {"id": "sleep_topk_qualities", "kind": "set",
         "q": "List sleep quality categories that account for at least 25% of nights.",
         "a": qualities_ge_25},
        {"id": "sleep_max_duration_date", "kind": "string",
         "q": "On which date (YYYY-MM-DD) did I sleep the longest?",
         "a": longest["date"] if longest else ""},
        {"id": "sleep_count_poor", "kind": "int",
         "q": "How many nights had poor sleep quality?",
         "a": len(poor)},
        {"id": "sleep_trend_q1_q2", "kind": "string",
         "q": "Did my average sleep duration increase, decrease, or stay the same from Q1 to Q2? (one word)",
         "a": trend},
    ]


# ---------------------------------------------------------------------------
# Schema 6: Workouts
# ---------------------------------------------------------------------------

WORKOUT_TYPES = ["cardio", "strength", "yoga", "swimming", "cycling", "hiit"]
WORKOUT_LOCATIONS = ["gym", "home", "park", "studio", "trail"]


def gen_workouts(seed: int, n: int) -> list[dict]:
    rng = _rng(seed)
    out = []
    start = date(2024, 1, 1)
    end = date(2024, 12, 31)
    for i in range(n):
        d = _date_in(rng, start, end)
        out.append({
            "id": i,
            "date": d.isoformat(),
            "type": rng.choice(WORKOUT_TYPES),
            "duration_min": rng.randint(15, 120),
            "calories_burned": rng.randint(80, 700),
            "location": rng.choice(WORKOUT_LOCATIONS),
        })
    out.sort(key=lambda r: r["date"])
    return out


def workout_questions(records: list[dict]) -> list[dict]:
    cardio = [r for r in records if r["type"] == "cardio"]
    by_type = Counter(r["type"] for r in records)
    top_type = by_type.most_common(1)[0][0] if by_type else None
    total_min = sum(r["duration_min"] for r in records)
    avg_cal = sum(r["calories_burned"] for r in records) / len(records) if records else 0
    long_workouts = [r for r in records if r["duration_min"] >= 60]
    summer = [r for r in records if "2024-06-01" <= r["date"] <= "2024-08-31"]
    home_strength = [r for r in records if r["location"] == "home" and r["type"] == "strength"]
    by_loc = Counter(r["location"] for r in records)
    locs_ge_25 = sorted({l for l, c in by_loc.items() if c / len(records) >= 0.25})
    q1 = [r for r in records if "2024-01-01" <= r["date"] <= "2024-03-31"]
    q2 = [r for r in records if "2024-04-01" <= r["date"] <= "2024-06-30"]
    trend = "increase" if len(q2) > len(q1) else ("decrease" if len(q2) < len(q1) else "same")
    return [
        {"id": "wo_count_cardio", "kind": "int",
         "q": "How many cardio workouts did I do?",
         "a": len(cardio)},
        {"id": "wo_sum_minutes", "kind": "float",
         "q": "What was my total workout time in minutes?",
         "a": _round(total_min)},
        {"id": "wo_avg_calories", "kind": "float",
         "q": "What was my average calories burned per workout? Round to 2 decimals.",
         "a": _round(avg_cal)},
        {"id": "wo_groupby_top_type", "kind": "string",
         "q": "What single workout type did I do most often?",
         "a": top_type},
        {"id": "wo_window_summer", "kind": "int",
         "q": "How many workouts did I do between 2024-06-01 and 2024-08-31 inclusive?",
         "a": len(summer)},
        {"id": "wo_multi_home_strength", "kind": "int",
         "q": "How many workouts were home strength sessions (location=home AND type=strength)?",
         "a": len(home_strength)},
        {"id": "wo_topk_locations", "kind": "set",
         "q": "List the workout locations that account for at least 25% of my workouts.",
         "a": locs_ge_25},
        {"id": "wo_long_count", "kind": "int",
         "q": "How many workouts lasted 60 minutes or longer?",
         "a": len(long_workouts)},
        {"id": "wo_total_calories", "kind": "int",
         "q": "What was my total calories burned across all workouts?",
         "a": sum(r["calories_burned"] for r in records)},
        {"id": "wo_trend_q1_q2", "kind": "string",
         "q": "Did my workout count increase, decrease, or stay the same from Q1 to Q2 2024? (one word)",
         "a": trend},
    ]


# ---------------------------------------------------------------------------
# Schema 7: Books
# ---------------------------------------------------------------------------

BOOK_GENRES = ["fiction", "non-fiction", "biography", "scifi", "fantasy",
               "mystery", "history", "self-help", "tech", "poetry"]
BOOK_TITLES = [(f"Book Title {i}", f"Author {chr(65 + i % 26)}") for i in range(60)]


def gen_books(seed: int, n: int) -> list[dict]:
    rng = _rng(seed)
    out = []
    start = date(2023, 1, 1)
    end = date(2025, 1, 1)
    titles = list(BOOK_TITLES)
    rng.shuffle(titles)
    for i in range(n):
        title, author = titles[i % len(titles)]
        st = _date_in(rng, start, end)
        days_to_finish = rng.randint(3, 60)
        ft = st + timedelta(days=days_to_finish)
        out.append({
            "id": i,
            "title": title,
            "author": author,
            "genre": rng.choice(BOOK_GENRES),
            "started_date": st.isoformat(),
            "finished_date": ft.isoformat(),
            "rating": rng.randint(1, 5),
            "pages": rng.randint(80, 900),
        })
    out.sort(key=lambda r: r["started_date"])
    return out


def book_questions(records: list[dict]) -> list[dict]:
    fiction = [r for r in records if r["genre"] == "fiction"]
    five_star = [r for r in records if r["rating"] == 5]
    finished_2024 = [r for r in records if r["finished_date"].startswith("2024")]
    avg_rating = sum(r["rating"] for r in records) / len(records) if records else 0
    by_genre = Counter(r["genre"] for r in records)
    top_genre = by_genre.most_common(1)[0][0] if by_genre else None
    long_books = [r for r in records if r["pages"] >= 500]
    avg_pages_scifi = (
        sum(r["pages"] for r in records if r["genre"] == "scifi")
        / max(1, sum(1 for r in records if r["genre"] == "scifi"))
    )
    genres_ge_15 = sorted({g for g, c in by_genre.items() if c / len(records) >= 0.15})
    longest_read = max(records, key=lambda r: (datetime.fromisoformat(r["finished_date"]) - datetime.fromisoformat(r["started_date"])).days) if records else None
    h1 = [r for r in records if r["finished_date"].startswith("2024") and r["finished_date"] <= "2024-06-30"]
    h2 = [r for r in records if r["finished_date"].startswith("2024") and r["finished_date"] >= "2024-07-01"]
    trend = "increase" if len(h2) > len(h1) else ("decrease" if len(h2) < len(h1) else "same")
    return [
        {"id": "books_count_fiction", "kind": "int",
         "q": "How many fiction-genre books did I read?",
         "a": len(fiction)},
        {"id": "books_count_five_star", "kind": "int",
         "q": "How many books did I rate 5 stars?",
         "a": len(five_star)},
        {"id": "books_avg_rating", "kind": "float",
         "q": "What is my average book rating? Round to 2 decimals.",
         "a": _round(avg_rating)},
        {"id": "books_groupby_top_genre", "kind": "string",
         "q": "What genre did I read most often?",
         "a": top_genre},
        {"id": "books_window_finished_2024", "kind": "int",
         "q": "How many books did I finish in calendar year 2024?",
         "a": len(finished_2024)},
        {"id": "books_multi_long_5star", "kind": "int",
         "q": "How many books were both 500+ pages AND rated 5 stars?",
         "a": sum(1 for r in records if r["pages"] >= 500 and r["rating"] == 5)},
        {"id": "books_topk_genres", "kind": "set",
         "q": "List genres that account for at least 15% of my books read.",
         "a": genres_ge_15},
        {"id": "books_avg_pages_scifi", "kind": "float",
         "q": "What is the average page count of scifi books I read? Round to 2 decimals.",
         "a": _round(avg_pages_scifi)},
        {"id": "books_long_count", "kind": "int",
         "q": "How many books had 500 or more pages?",
         "a": len(long_books)},
        {"id": "books_trend_2024_h1_h2", "kind": "string",
         "q": "Did my finished-book count increase, decrease, or stay the same from H1 to H2 of 2024? (one word)",
         "a": trend},
    ]


# ---------------------------------------------------------------------------
# Schema 8: Medical visits
# ---------------------------------------------------------------------------

VISIT_TYPES = ["annual-checkup", "dental", "specialist", "urgent-care",
               "vision", "physical-therapy", "vaccination", "mental-health"]
DOCTORS = ["Dr. Patel", "Dr. Kim", "Dr. Garcia", "Dr. Smith", "Dr. Chen",
           "Dr. Nguyen", "Dr. Johnson", "Dr. Lee"]
CONDITIONS = ["seasonal-allergies", "back-pain", "migraine", "anxiety",
              "high-blood-pressure", "asthma", "tooth-decay", "eye-strain"]
MEDICATIONS = ["lisinopril", "ibuprofen", "fluoxetine", "loratadine",
               "albuterol", "amoxicillin", "metformin"]


def gen_medical(seed: int, n: int) -> list[dict]:
    rng = _rng(seed)
    out = []
    start = date(2022, 1, 1)
    end = date(2025, 6, 1)
    for i in range(n):
        d = _date_in(rng, start, end)
        n_cond = rng.randint(0, 2)
        n_med = rng.randint(0, 2)
        out.append({
            "id": i,
            "date": d.isoformat(),
            "type": rng.choice(VISIT_TYPES),
            "doctor": rng.choice(DOCTORS),
            "conditions": sorted(rng.sample(CONDITIONS, k=n_cond)),
            "medications": sorted(rng.sample(MEDICATIONS, k=n_med)),
            "cost_usd": _round(rng.uniform(20, 500)),
        })
    out.sort(key=lambda r: r["date"])
    return out


def medical_questions(records: list[dict]) -> list[dict]:
    dental = [r for r in records if r["type"] == "dental"]
    by_type = Counter(r["type"] for r in records)
    top_type = by_type.most_common(1)[0][0] if by_type else None
    total_cost = sum(r["cost_usd"] for r in records)
    avg_cost = total_cost / len(records) if records else 0
    has_med = [r for r in records if r["medications"]]
    yr_24 = [r for r in records if r["date"].startswith("2024")]
    migraine = [r for r in records if "migraine" in r["conditions"]]
    by_doc = Counter(r["doctor"] for r in records)
    docs_ge_15 = sorted({d for d, c in by_doc.items() if c / len(records) >= 0.15})
    yr_22 = sum(1 for r in records if r["date"].startswith("2022"))
    yr_24c = sum(1 for r in records if r["date"].startswith("2024"))
    trend = "increase" if yr_24c > yr_22 else ("decrease" if yr_24c < yr_22 else "same")
    no_meds_no_conds = [r for r in records if not r["medications"] and not r["conditions"]]
    return [
        {"id": "med_count_dental", "kind": "int",
         "q": "How many dental visits did I have?",
         "a": len(dental)},
        {"id": "med_sum_cost", "kind": "float",
         "q": "What was my total medical cost in USD across all visits?",
         "a": _round(total_cost)},
        {"id": "med_avg_cost", "kind": "float",
         "q": "What was my average cost per medical visit in USD? Round to 2 decimals.",
         "a": _round(avg_cost)},
        {"id": "med_groupby_top_type", "kind": "string",
         "q": "Which visit type appears most often?",
         "a": top_type},
        {"id": "med_window_2024", "kind": "int",
         "q": "How many medical visits did I have in calendar year 2024?",
         "a": len(yr_24)},
        {"id": "med_multi_24_with_meds", "kind": "int",
         "q": "How many 2024 medical visits resulted in at least one medication being prescribed?",
         "a": sum(1 for r in yr_24 if r["medications"])},
        {"id": "med_topk_doctors", "kind": "set",
         "q": "List doctors who account for at least 15% of all my visits.",
         "a": docs_ge_15},
        {"id": "med_count_migraine", "kind": "int",
         "q": "How many medical visits noted 'migraine' as a condition?",
         "a": len(migraine)},
        {"id": "med_count_clean", "kind": "int",
         "q": "How many medical visits had neither conditions nor medications recorded?",
         "a": len(no_meds_no_conds)},
        {"id": "med_trend_22_24", "kind": "string",
         "q": "Did my medical visit count increase, decrease, or stay the same from 2022 to 2024? (one word)",
         "a": trend},
    ]


# ---------------------------------------------------------------------------
# Schema 9: Work meetings
# ---------------------------------------------------------------------------

MEETING_TOPICS = ["roadmap", "design-review", "1on1", "standup", "interview",
                  "client-pitch", "retrospective", "planning", "training", "all-hands"]
MEETING_TYPES = ["1on1", "team", "external", "all-hands"]


def gen_meetings(seed: int, n: int) -> list[dict]:
    rng = _rng(seed)
    out = []
    start = date(2024, 1, 1)
    end = date(2024, 12, 31)
    for i in range(n):
        d = _date_in(rng, start, end)
        n_attendees = rng.randint(2, 12)
        out.append({
            "id": i,
            "date": d.isoformat(),
            "time": f"{rng.randint(8, 17):02d}:{rng.choice([0, 30]):02d}",
            "duration_min": rng.choice([15, 30, 45, 60, 90]),
            "n_attendees": n_attendees,
            "topic": rng.choice(MEETING_TOPICS),
            "type": rng.choice(MEETING_TYPES),
        })
    out.sort(key=lambda r: r["date"])
    return out


def meeting_questions(records: list[dict]) -> list[dict]:
    one_on_one = [r for r in records if r["type"] == "1on1"]
    by_topic = Counter(r["topic"] for r in records)
    top_topic = by_topic.most_common(1)[0][0] if by_topic else None
    total_min = sum(r["duration_min"] for r in records)
    avg_attendees = sum(r["n_attendees"] for r in records) / len(records) if records else 0
    long = [r for r in records if r["duration_min"] >= 60]
    morning = [r for r in records if r["time"] < "12:00"]
    big = [r for r in records if r["n_attendees"] >= 8]
    by_type = Counter(r["type"] for r in records)
    types_ge_25 = sorted({t for t, c in by_type.items() if c / len(records) >= 0.25})
    h1 = [r for r in records if "2024-01-01" <= r["date"] <= "2024-06-30"]
    h2 = [r for r in records if "2024-07-01" <= r["date"] <= "2024-12-31"]
    trend = "increase" if len(h2) > len(h1) else ("decrease" if len(h2) < len(h1) else "same")
    return [
        {"id": "meet_count_1on1", "kind": "int",
         "q": "How many 1on1 meetings did I have?",
         "a": len(one_on_one)},
        {"id": "meet_sum_minutes", "kind": "float",
         "q": "What was my total meeting time in minutes?",
         "a": _round(total_min)},
        {"id": "meet_avg_attendees", "kind": "float",
         "q": "What was the average number of attendees per meeting? Round to 2 decimals.",
         "a": _round(avg_attendees)},
        {"id": "meet_groupby_top_topic", "kind": "string",
         "q": "Which meeting topic appears most often?",
         "a": top_topic},
        {"id": "meet_window_morning", "kind": "int",
         "q": "How many meetings started before 12:00?",
         "a": len(morning)},
        {"id": "meet_multi_long_big", "kind": "int",
         "q": "How many meetings were both 60+ minutes AND had 8 or more attendees?",
         "a": sum(1 for r in records if r["duration_min"] >= 60 and r["n_attendees"] >= 8)},
        {"id": "meet_topk_types", "kind": "set",
         "q": "List meeting types that account for at least 25% of all my meetings.",
         "a": types_ge_25},
        {"id": "meet_long_count", "kind": "int",
         "q": "How many meetings lasted 60 minutes or longer?",
         "a": len(long)},
        {"id": "meet_big_count", "kind": "int",
         "q": "How many meetings had 8 or more attendees?",
         "a": len(big)},
        {"id": "meet_trend_h1_h2", "kind": "string",
         "q": "Did my meeting count increase, decrease, or stay the same from H1 to H2 2024? (one word)",
         "a": trend},
    ]


# ---------------------------------------------------------------------------
# Schema 10: Purchases
# ---------------------------------------------------------------------------

PURCHASE_CATEGORIES = ["electronics", "clothing", "books", "groceries",
                       "home", "tools", "toys", "beauty", "sports", "food"]
PURCHASE_STORES = ["Amazon", "BigBox", "GreenMart", "TechStore", "FashionCo",
                   "BookHaven", "ToolWorld", "Sportie", "Beautique"]


def gen_purchases(seed: int, n: int) -> list[dict]:
    rng = _rng(seed)
    out = []
    start = date(2024, 1, 1)
    end = date(2024, 12, 31)
    for i in range(n):
        d = _date_in(rng, start, end)
        cat = rng.choice(PURCHASE_CATEGORIES)
        out.append({
            "id": i,
            "date": d.isoformat(),
            "item": f"item-{i}",
            "price_usd": _round(rng.uniform(5, 1500)),
            "store": rng.choice(PURCHASE_STORES),
            "category": cat,
            "online": rng.random() < 0.55,
        })
    out.sort(key=lambda r: r["date"])
    return out


def purchase_questions(records: list[dict]) -> list[dict]:
    online = [r for r in records if r["online"]]
    by_cat = Counter(r["category"] for r in records)
    top_cat = by_cat.most_common(1)[0][0] if by_cat else None
    total = sum(r["price_usd"] for r in records)
    expensive = [r for r in records if r["price_usd"] >= 500]
    avg_electronics = (
        sum(r["price_usd"] for r in records if r["category"] == "electronics")
        / max(1, sum(1 for r in records if r["category"] == "electronics"))
    )
    h1 = [r for r in records if "2024-01-01" <= r["date"] <= "2024-06-30"]
    h2 = [r for r in records if "2024-07-01" <= r["date"] <= "2024-12-31"]
    trend = "increase" if len(h2) > len(h1) else ("decrease" if len(h2) < len(h1) else "same")
    by_store = Counter(r["store"] for r in records)
    stores_ge_15 = sorted({s for s, c in by_store.items() if c / len(records) >= 0.15})
    online_books = [r for r in records if r["online"] and r["category"] == "books"]
    top_store = by_store.most_common(1)[0][0] if by_store else None
    return [
        {"id": "buy_count_online", "kind": "int",
         "q": "How many online purchases did I make?",
         "a": len(online)},
        {"id": "buy_sum_total", "kind": "float",
         "q": "What was my total spending on purchases in USD?",
         "a": _round(total)},
        {"id": "buy_avg_electronics", "kind": "float",
         "q": "What was my average price for electronics-category purchases? Round to 2 decimals.",
         "a": _round(avg_electronics)},
        {"id": "buy_groupby_top_category", "kind": "string",
         "q": "What single category did I purchase from most often?",
         "a": top_cat},
        {"id": "buy_window_h2", "kind": "int",
         "q": "How many purchases did I make between 2024-07-01 and 2024-12-31 inclusive?",
         "a": len(h2)},
        {"id": "buy_multi_online_books", "kind": "int",
         "q": "How many of my purchases were online books-category?",
         "a": len(online_books)},
        {"id": "buy_topk_stores", "kind": "set",
         "q": "List stores that account for at least 15% of all my purchases.",
         "a": stores_ge_15},
        {"id": "buy_expensive_count", "kind": "int",
         "q": "How many purchases were 500 USD or more?",
         "a": len(expensive)},
        {"id": "buy_top_store", "kind": "string",
         "q": "What store did I purchase from most often?",
         "a": top_store},
        {"id": "buy_trend_h1_h2", "kind": "string",
         "q": "Did my purchase count increase, decrease, or stay the same from H1 to H2 2024? (one word)",
         "a": trend},
    ]


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

SCHEMAS: dict[str, dict[str, Any]] = {
    "trips": {"gen": gen_trips, "qfn": trip_questions, "label": "Trips"},
    "contacts": {"gen": gen_contacts, "qfn": contact_questions, "label": "Contacts"},
    "meals": {"gen": gen_meals, "qfn": meal_questions, "label": "Meals"},
    "transactions": {"gen": gen_transactions, "qfn": transaction_questions, "label": "Transactions"},
    "sleep": {"gen": gen_sleep, "qfn": sleep_questions, "label": "Sleep log"},
    "workouts": {"gen": gen_workouts, "qfn": workout_questions, "label": "Workouts"},
    "books": {"gen": gen_books, "qfn": book_questions, "label": "Books"},
    "medical": {"gen": gen_medical, "qfn": medical_questions, "label": "Medical visits"},
    "meetings": {"gen": gen_meetings, "qfn": meeting_questions, "label": "Meetings"},
    "purchases": {"gen": gen_purchases, "qfn": purchase_questions, "label": "Purchases"},
}
