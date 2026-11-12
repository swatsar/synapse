"""Grounded self-inspection of Synapse's real growth and training state.

The model has no privileged introspection into its hidden weights. This skill
therefore reports facts from real artifacts -- the mycelial growth graph, the
autonomy state, promoted adapter manifests and the verified experience store --
and derives concrete improvement actions from them. It exists so that requests
such as "изучи себя" produce a self-report about Synapse, not generic advice
addressed to the user.
"""
from __future__ import annotations

PROTOCOL_VERSION: str = "1.0"

import json
import re
from pathlib import Path
from typing import Any

from synapse.core.models import ExecutionContext


_BLOCKER_LABELS = {
    "auto_train_disabled": "автообучение отключено",
    "not_enough_verified_experience": "недостаточно проверенного опыта",
    "no_new_verified_experience": "нет нового проверенного опыта",
    "cooldown": "действует пауза между обучениями",
    "training_already_running": "обучение уже выполняется",
}

_RETROSPECTIVE_CUES = (
    "что ты узнал", "что ты узнала", "чему ты научился",
    "чему ты научилась", "чему научился", "чему научилась",
    "что ты выучил", "что ты выучила", "что ты запомнил",
    "что ты запомнила", "что ты усвоил", "что ты усвоила",
    "какие знания ты получил", "какие знания ты получила",
    "what did you learn", "what have you learned",
)

_QUESTION_RECORD_CUES = (
    "что ты узнал", "что ты узнала", "чему ты научился",
    "чему ты научилась", "чему научился", "чему научилась",
    "что ты выучил", "что ты выучила", "что ты запомнил",
    "что ты запомнила", "что ты усвоил", "что ты усвоила",
    "what did you learn", "what have you learned",
)


def _workspace(ctx: ExecutionContext, path: str = ".") -> Path:
    root = None
    if ctx.memory_store is not None:
        root = getattr(ctx.memory_store, "workspace_root", None)
    candidate = Path(path or ".").expanduser()
    if root is not None and not candidate.is_absolute():
        candidate = Path(root) / candidate
    return candidate.resolve()


def _read_training_manifest(adapter_path: str | None) -> dict[str, Any]:
    if not adapter_path:
        return {}
    manifest_file = Path(adapter_path) / "training_manifest.json"
    try:
        payload = json.loads(manifest_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _adapter_snapshot() -> dict[str, Any]:
    from synapse.llm.local_model import adapter_status
    from synapse.models import get_model_registry

    manifests = [
        manifest for manifest in get_model_registry().list()
        if manifest.status == "downloaded" and manifest.local_path
    ]
    if not manifests:
        return {
            "status": "no_local_model",
            "model_id": None,
            "selected": False,
            "applied": False,
            "adapter_path": None,
            "training": {},
        }
    manifest = manifests[0]
    status = adapter_status(manifest.local_path)
    training = _read_training_manifest(status.get("adapter_path"))
    return {
        **status,
        "status": "ready",
        "model_id": manifest.model_id,
        "training": {
            key: training.get(key)
            for key in (
                "run_id", "holdout_loss_before", "holdout_loss_after",
                "promotion_gate", "promotion_status", "behavioral_probes",
                "behavioral_passed_before", "behavioral_passed_after",
                "behavioral_gate", "steps",
            )
            if training.get(key) is not None
        },
    }


def _growth_snapshot(workspace: Path) -> dict[str, Any]:
    from synapse.growth import get_growth_network

    network = get_growth_network(workspace)
    status = network.status()
    paths = network.recent_paths(limit=200)
    skills: set[str] = set()
    for path in paths:
        relation = path.get("relation")
        if relation == "activates":
            # task --activates--> skill
            skills.add(str(path.get("target") or ""))
        elif relation == "co_activates":
            skills.add(str(path.get("source") or ""))
            skills.add(str(path.get("target") or ""))
    skills.discard("")
    return {**status, "skills": sorted(skills)}


def _autonomy_snapshot(workspace: Path) -> dict[str, Any]:
    from synapse.growth import get_autonomy_loop

    return get_autonomy_loop(workspace).status()


def _experience_snapshot(workspace: Path, focus: str = "") -> dict[str, Any]:
    from synapse.experience import ExperienceStore

    db_path = workspace / ".synapse" / "experience.sqlite3"
    if not db_path.is_file():
        return {"total": 0, "verified": 0}
    store = ExperienceStore(db_path)
    try:
        snapshot = {"total": store.count(), "verified": store.count(verified_only=True)}
        if _is_retrospective_question(focus):
            snapshot["learned"] = _learned_snapshot(store, focus)
        return snapshot
    finally:
        store.close()


def _is_retrospective_question(focus: str) -> bool:
    text = (focus or "").lower()
    return any(cue in text for cue in _RETROSPECTIVE_CUES)


def _extract_learning_topic(focus: str) -> str | None:
    """Extract the past task a retrospective question refers to.

    The user usually quotes the original task, for example:
    «а что ты узнал когда выполнял это задание: "научись ..."».
    Quotes are the most reliable marker; otherwise the question wrapper is
    stripped so the remaining text can be matched against experience records.
    """
    text = (focus or "").strip()
    if not text:
        return None
    quoted = re.findall(r"[\"«“']([^\"»”']{3,300})[\"»”']", text)
    if quoted:
        topic = max(quoted, key=len)
    else:
        topic = re.sub(
            r"^(?:а\s+)?(?:что|чему|какие|каких)\s+ты\s+"
            r"(?:узнал\w*|научил\w*|выучил\w*|запомнил\w*|усвоил\w*)\s*",
            "",
            text,
            flags=re.IGNORECASE,
        )
        topic = re.sub(
            r"^(?:what|which)\s+(?:did|have)\s+you\s+learn(?:ed)?\s*",
            "",
            topic,
            flags=re.IGNORECASE,
        )
        topic = re.sub(
            r"^(?:при\s+выполнении|во\s+время\s+выполнения|выполняя)\s*"
            r"(?:задани\w*|задач\w*)?\s*",
            "",
            topic,
            flags=re.IGNORECASE,
        )
        topic = re.sub(
            r"^(?:когда|пока|во\s+время|при|выполняя)\b[^:：]*[:\-–—]\s*",
            "",
            topic,
            flags=re.IGNORECASE,
        )
        topic = re.sub(
            r"^(?:when|while|from)\s+(?:doing|performing|completing|working\s+on)?"
            r"\s*(?:the\s+)?(?:task|job)?\s*[:\-]?\s*",
            "",
            topic,
            flags=re.IGNORECASE,
        )
    topic = topic.strip().strip("\"'«»“”").strip(" .,:;!?-–—")
    if len(topic) < 4:
        return None
    if any(cue in topic.lower() for cue in _QUESTION_RECORD_CUES):
        return None
    return topic


def _topic_keys(value: str) -> set[str]:
    tokens = re.findall(r"[0-9a-zа-яё]+", (value or "").lower())
    return {token[:6] for token in tokens if len(token) >= 4}


def _learning_pair(record: Any) -> tuple[str, str] | None:
    feedback = getattr(record, "feedback", None) or {}
    text = str(
        feedback.get("training_text")
        or feedback.get("candidate_training_text")
        or ""
    )
    if "Assistant:" not in text:
        return None
    user_part, assistant_part = text.split("Assistant:", 1)
    question = user_part.replace("User:", "", 1).strip()
    answer = assistant_part.strip()
    if len(question) < 4 or len(answer) < 8:
        return None
    return question, answer


def _is_question_record(record: Any) -> bool:
    objective = str(getattr(record, "objective", "") or "").lower()
    return any(cue in objective for cue in _QUESTION_RECORD_CUES)


def _learned_snapshot(store: Any, focus: str) -> dict[str, Any]:
    """Return verified learning-loop Q/A pairs relevant to a retrospective question.

    Records created by the old misrouting bug used the question itself as the
    learning topic; they are excluded so the report cannot quote its own
    accidental garbage back as knowledge.
    """
    topic = _extract_learning_topic(focus)
    keys = _topic_keys(topic) if topic else set()
    matched: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for record in store.list_records(verified_only=True, limit=5000):
        if str(getattr(record, "executor", "")) != "learning_loop":
            continue
        if _is_question_record(record):
            continue
        if keys:
            objective_keys = _topic_keys(str(getattr(record, "objective", "") or ""))
            if len(keys & objective_keys) / len(keys) < 0.5:
                continue
        pair = _learning_pair(record)
        if pair is None or pair in seen:
            continue
        seen.add(pair)
        inputs = getattr(record, "inputs", None) or {}
        teacher_evidence = inputs.get("teacher_evidence") if isinstance(inputs, dict) else None
        teacher = None
        if isinstance(teacher_evidence, dict):
            teacher = teacher_evidence.get("teacher") or teacher_evidence.get("kind")
        matched.append({
            "question": pair[0],
            "answer": pair[1],
            "teacher": teacher or getattr(record, "model", None),
            "created_at": getattr(record, "created_at", None),
            "run_id": getattr(record, "run_id", None),
        })
    limit = 5 if keys else 3
    return {
        "mode": "topic" if keys else "latest",
        "topic": topic,
        "records": len(matched),
        "items": matched[:limit],
    }


def _learned_findings(experience: dict[str, Any]) -> list[dict[str, Any]]:
    learned = experience.get("learned") or {}
    if not learned:
        return []
    items = learned.get("items") or []
    topic = learned.get("topic")
    if items:
        evidence = (
            f"по заданию «{topic}» найдено {learned.get('records', len(items))} "
            "проверенных учебных пар"
            if topic else
            f"в проверенном опыте есть {learned.get('records', len(items))} "
            "недавних учебных пар"
        )
        return [{
            "area": "recall",
            "evidence": evidence,
            "conclusion": (
                "ответ собран из сохранённых учебных пар, а не из "
                "предположений о скрытых весах"
            ),
        }]
    if topic:
        return [{
            "area": "recall",
            "evidence": f"по заданию «{topic}» проверенных учебных пар не найдено",
            "conclusion": (
                "нельзя утверждать, что именно усвоено: в опыте нет записи "
                "с независимым подтверждением знаний"
            ),
        }]
    return []


def _growth_findings(growth: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    events = int(growth.get("events") or 0)
    nodes = int(growth.get("nodes") or 0)
    edges = int(growth.get("edges") or 0)
    myelinated = int(growth.get("myelinated_paths") or 0)
    coactivations = int(growth.get("coactivation_paths") or 0)

    if events == 0:
        findings.append({
            "area": "growth",
            "evidence": "0 событий обучения в мицелиальной сети",
            "conclusion": "сеть ещё не начала расти: нет подтверждённых маршрутов задача → навык",
        })
    else:
        findings.append({
            "area": "growth",
            "evidence": (
                f"{events} событий, {nodes} узлов, {edges} связей, "
                f"{myelinated} миелинизированных путей, {coactivations} ко-активаций"
            ),
            "conclusion": (
                "сеть накапливает опыт, но ассоциативные связи между навыками "
                "пока не сформированы"
                if coactivations == 0
                else "сеть накапливает опыт и строит ассоциативные связи"
            ),
        })

    weak = growth.get("weak_paths") or []
    if weak:
        labels = [f"{item.get('source')} → {item.get('target')}" for item in weak[:3]]
        findings.append({
            "area": "growth",
            "evidence": "слабые пути: " + "; ".join(labels),
            "conclusion": "эти маршруты чаще проваливались, чем удавались, и должны тормозиться",
        })
    return findings


def _training_findings(
    adapter: dict[str, Any],
    autonomy: dict[str, Any],
    experience: dict[str, Any],
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    readiness = autonomy.get("training_readiness") or {}
    blockers = [
        _BLOCKER_LABELS.get(item, str(item))
        for item in (readiness.get("blockers") or [])
    ]
    findings.append({
        "area": "training",
        "evidence": (
            f"проверенного опыта: {experience.get('verified', 0)}"
            f" (всего записей: {experience.get('total', 0)}); "
            f"готовность: {'да' if readiness.get('ready') else 'нет'}"
        ),
        "conclusion": (
            "можно запускать обучение"
            if readiness.get("ready")
            else "обучение заблокировано: " + (", ".join(blockers) or "нет данных")
        ),
    })

    study = autonomy.get("last_self_study_result") or {}
    if autonomy.get("self_study_enabled"):
        if study:
            findings.append({
                "area": "training",
                "evidence": (
                    "самообучение по документации: последний проход создал "
                    f"{study.get('created', 0)} проверенных фактов "
                    f"(пропущено {study.get('skipped', 0)})"
                ),
                "conclusion": (
                    "цикл пополняет опыт без внешнего учителя"
                    if int(study.get("created") or 0) > 0
                    else "источники не дали новых фактов: нужны новые документы или задачи"
                ),
            })
        else:
            findings.append({
                "area": "training",
                "evidence": "самообучение по документации включено, но ещё не запускалось",
                "conclusion": "при нехватке опыта цикл сам изучит README и docs",
            })

    if adapter.get("status") == "no_local_model":
        findings.append({
            "area": "training",
            "evidence": "нет скачанной локальной модели",
            "conclusion": "обучать и применять адаптер не к чему",
        })
        return findings

    training = adapter.get("training") or {}
    if adapter.get("selected"):
        loss = ""
        if training.get("holdout_loss_before") is not None and training.get("holdout_loss_after") is not None:
            loss = (
                f"; holdout loss {training['holdout_loss_before']:.4f} → "
                f"{training['holdout_loss_after']:.4f}"
            )
        findings.append({
            "area": "training",
            "evidence": (
                f"выбран адаптер {adapter.get('adapter_name') or adapter.get('adapter_path')}"
                f"{loss}; promotion={training.get('promotion_status') or 'нет манифеста'}"
            ),
            "conclusion": (
                "адаптер применён при инференсе"
                if adapter.get("applied")
                else "адаптер выбран и будет применён при следующей загрузке модели"
            ),
        })
    else:
        findings.append({
            "area": "training",
            "evidence": "promoted-адаптер не найден",
            "conclusion": "обучение ещё не изменило инференс: модель отвечает базовыми весами",
        })
    return findings


def _engineering_findings(growth: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    skills = set(growth.get("skills") or [])
    if "code_generator" in skills:
        findings.append({
            "area": "engineering",
            "evidence": "в сети есть успешный маршрут code_generator",
            "conclusion": "генерация кода уже подкреплена опытом и может миелинизироваться",
        })
    if "code_generator" in skills and not ({"workspace_audit", "security_audit"} & skills):
        findings.append({
            "area": "engineering",
            "evidence": "code_generator есть, а проверочных навыков в сети нет",
            "conclusion": "код генерируется без закреплённой связи с аудитом/проверкой",
        })
    if growth.get("fast_paths"):
        top = growth["fast_paths"][:3]
        findings.append({
            "area": "engineering",
            "evidence": "быстрые пути: " + "; ".join(
                f"{item.get('source')} → {item.get('target')} (w={item.get('weight')})"
                for item in top
            ),
            "conclusion": "повторяющиеся успешные маршруты становятся автоматизмами",
        })
    return findings


def _recommendations(
    growth: dict[str, Any],
    autonomy: dict[str, Any],
    adapter: dict[str, Any],
    experience: dict[str, Any],
) -> list[dict[str, Any]]:
    recommendations: list[dict[str, Any]] = []
    readiness = autonomy.get("training_readiness") or {}
    blockers = set(readiness.get("blockers") or [])

    if adapter.get("status") == "no_local_model":
        recommendations.append({
            "priority": 1,
            "action": "Скачать локальную модель и проверить её загрузку",
            "reason": "без локальных весов невозможны ни инференс, ни LoRA-обучение",
        })
    elif not adapter.get("selected"):
        recommendations.append({
            "priority": 1,
            "action": "Запустить обучение LoRA-адаптера на проверенном опыте",
            "reason": "promoted-адаптер ещё не создан, поэтому опыт не меняет ответы модели",
        })
    elif not adapter.get("applied"):
        recommendations.append({
            "priority": 2,
            "action": "Выполнить один инференс и подтвердить adapter_applied=true",
            "reason": "адаптер выбран, но фактическое применение ещё не подтверждено",
        })

    if "not_enough_verified_experience" in blockers:
        recommendations.append({
            "priority": 1,
            "action": (
                "Выполнять задачи с acceptance_criteria и независимой проверкой, "
                "пока проверенных записей не станет не меньше "
                f"{readiness.get('required_records', 0)}"
            ),
            "reason": f"сейчас проверено {readiness.get('verified_records', 0)} записей",
        })
    if "no_new_verified_experience" in blockers:
        study = autonomy.get("last_self_study_result") or {}
        created = int(study.get("created") or 0)
        if autonomy.get("self_study_enabled"):
            recommendations.append({
                "priority": 2,
                "action": (
                    "Дать автономному циклу обучить адаптер на фактах, добавленных самообучением"
                    if created
                    else "Пополнить документацию проекта или выполнить новые задачи с критериями приёмки"
                ),
                "reason": (
                    f"самообучение добавило {created} проверенных фактов"
                    if created
                    else "самообучение включено, но новых проверенных фактов пока нет"
                ),
            })
        else:
            recommendations.append({
                "priority": 2,
                "action": (
                    "Одобрять или отклонять реальные ответы через feedback и накопить "
                    f"ещё {readiness.get('required_new_records', 0)} новых проверенных записей"
                ),
                "reason": "обучение не повторится на тех же данных: нужен новый подтверждённый опыт",
            })
    if "cooldown" in blockers:
        recommendations.append({
            "priority": 3,
            "action": "Дождаться конца паузы или запустить обучение после появления нового опыта",
            "reason": "защита от переобучения на одном и том же наборе",
        })
    if "auto_train_disabled" in blockers:
        recommendations.append({
            "priority": 2,
            "action": "Включить автообучение в конфигурации автономного цикла",
            "reason": "без этого цикл не запускает обучение сам",
        })

    coactivations = int(growth.get("coactivation_paths") or 0)
    if coactivations == 0:
        recommendations.append({
            "priority": 2,
            "action": "Выполнять многошаговые задачи (например, код → проверка → запись файла)",
            "reason": "ко-активаций 0: навыки пока не связываются в ассоциативную сеть",
        })
    skills = set(growth.get("skills") or [])
    if "code_generator" in skills and not ({"workspace_audit", "security_audit"} & skills):
        recommendations.append({
            "priority": 2,
            "action": (
                "Связывать code_generator с workspace_audit или security_audit "
                "в одной успешной задаче"
            ),
            "reason": (
                "код генерируется без закреплённой связи с проверкой; "
                "ко-активация сделает проверку частью автоматического маршрута"
            ),
        })
    if growth.get("weak_paths"):
        recommendations.append({
            "priority": 3,
            "action": "Разобрать слабые маршруты и исправить повторяющиеся ошибки навыков",
            "reason": "слабые пути тормозят recall и могут отравлять обучение",
        })
    if int(experience.get("verified") or 0) < 8:
        recommendations.append({
            "priority": 2,
            "action": "Сначала нарастить небольшой, но чистый набор проверенных примеров",
            "reason": "на малом объёме адаптер легко переобучается и теряет базовые ответы",
        })
    recommendations.append({
        "priority": 4,
        "action": "После каждого успешного цикла проверять holdout loss и поведенческие пробы",
        "reason": "снижение loss само по себе не доказывает, что ответы стали лучше",
    })
    return recommendations


def _render_content(
    *,
    focus: str,
    growth: dict[str, Any],
    autonomy: dict[str, Any],
    adapter: dict[str, Any],
    experience: dict[str, Any],
    findings: list[dict[str, Any]],
    recommendations: list[dict[str, Any]],
) -> str:
    readiness = autonomy.get("training_readiness") or {}
    study = autonomy.get("last_self_study_result") or {}
    lines: list[str] = [
        "Самоинспекция Synapse по реальным артефактам (не общие советы человеку).",
        "",
    ]
    learned = experience.get("learned") or {}
    if learned:
        topic = learned.get("topic")
        lines.append(
            f"Ответ по указанному заданию: «{topic}»."
            if topic else "Ответ про недавнее обучение:"
        )
        items = learned.get("items") or []
        if items:
            lines.append(
                f"В проверенном опыте найдено {learned.get('records', len(items))} "
                "учебных пар; вот что сохранилось:"
            )
            for index, item in enumerate(items[:5], start=1):
                lines.append(f"{index}. Вопрос: {item['question']}")
                lines.append(
                    f"   Ответ: {item['answer']} "
                    f"(запись {str(item.get('created_at') or '')[:10]})"
                )
        elif topic:
            lines.append(
                "- Проверенных учебных пар по этому заданию нет. В опыте есть "
                "только факт выполнения, поэтому я не могу утверждать, что "
                "именно было усвоено."
            )
        else:
            lines.append("- Проверенных учебных пар в опыте пока нет.")
        lines.append("")
    lines.append("Что я вижу о себе:")
    lines.extend(f"- {item['evidence']} — {item['conclusion']}." for item in findings)

    lines.extend([
        "",
        "Текущее состояние:",
        (
            f"- Локальная модель: {adapter.get('model_id') or 'не загружена'}; "
            f"адаптер: {adapter.get('adapter_name') or 'нет'}; "
            f"применён при инференсе: {'да' if adapter.get('applied') else 'нет'}."
        ),
        (
            f"- Сеть роста: событий {growth.get('events', 0)}, узлов {growth.get('nodes', 0)}, "
            f"связей {growth.get('edges', 0)}, миелинизировано {growth.get('myelinated_paths', 0)}, "
            f"ко-активаций {growth.get('coactivation_paths', 0)}, "
            f"консолидаций {growth.get('consolidation_passes', 0)}."
        ),
        (
            f"- Проверенный опыт: {experience.get('verified', 0)} из {experience.get('total', 0)} записей; "
            f"готовность к обучению: {'да' if readiness.get('ready') else 'нет'}."
        ),
        (
            f"- Автономный цикл: {autonomy.get('status', 'неизвестно')}; "
            f"автообучение: {'включено' if autonomy.get('auto_train_enabled') else 'выключено'}; "
            f"последнее обучение: {autonomy.get('last_train_status') or 'ещё не запускалось'}."
        ),
        (
            f"- Самообучение по документации: "
            f"{'включено' if autonomy.get('self_study_enabled') else 'выключено'}; "
            f"последний проход: "
            f"{study.get('created', 0) if study else 'не запускался'} проверенных фактов."
        ),
    ])

    if recommendations:
        lines.extend(["", "Что улучшить в разработке и саморазвитии (по приоритету):"])
        for index, item in enumerate(
            sorted(recommendations, key=lambda value: value["priority"]), start=1,
        ):
            lines.append(f"{index}. {item['action']}. Причина: {item['reason']}.")

    lines.extend([
        "",
        "Как устроено моё развитие (реальные механизмы):",
        "- Успешный маршрут усиливает связь задача → навык, ошибка тормозит её; "
        "после трёх успехов и достаточного веса путь миелинизируется.",
        "- Консолидация ослабляет слабые связи, удаляет мёртвые и воспроизводит "
        "успешные быстрые пути, чтобы они не забывались.",
        "- Ко-активация связывает навыки, сработавшие вместе, и recall предлагает "
        "партнёра даже без прямого маршрута.",
        "- Обучение использует только проверенный опыт; адаптер допускается к "
        "инференсу после улучшения holdout loss и отсутствия поведенческой регрессии.",
        "",
        "Границы честности:",
        "- Я не читаю скрытые состояния весов и не выдумываю выполненные действия; "
        "выводы построены на графе роста, манифестах адаптера, состоянии автономии и базе опыта.",
        (
            "- Запрос учтён: " + (focus[:300] if focus else "самоинспекция")
        ),
    ])
    return "\n".join(lines)


async def execute_self_inspection(
    ctx: ExecutionContext,
    focus: str = "",
    path: str = ".",
    **_: Any,
) -> dict[str, Any]:
    """Report Synapse's real state and derive concrete self-development actions."""
    if not any(value.startswith("memory:read") for value in ctx.capabilities):
        return {"success": False, "error": "Capability denied: memory:read"}
    if not any(value.startswith("fs:read") for value in ctx.capabilities):
        return {"success": False, "error": "Capability denied: fs:read"}

    workspace = _workspace(ctx, path)
    try:
        growth = _growth_snapshot(workspace)
        autonomy = _autonomy_snapshot(workspace)
        adapter = _adapter_snapshot()
        experience = _experience_snapshot(workspace, focus)
    except Exception as exc:  # pragma: no cover - defensive, surfaced honestly
        return {
            "success": False,
            "error": f"Self-inspection failed: {exc}",
            "protocol_version": PROTOCOL_VERSION,
        }

    findings = (
        _growth_findings(growth)
        + _training_findings(adapter, autonomy, experience)
        + _engineering_findings(growth)
        + _learned_findings(experience)
    )
    recommendations = _recommendations(growth, autonomy, adapter, experience)
    content = _render_content(
        focus=focus,
        growth=growth,
        autonomy=autonomy,
        adapter=adapter,
        experience=experience,
        findings=findings,
        recommendations=recommendations,
    )
    return {
        "success": True,
        "content": content,
        "provider": "synapse_self_inspection",
        "model": adapter.get("model_id"),
        "focus": focus,
        "findings": findings,
        "recommendations": recommendations,
        "growth": {
            key: growth.get(key)
            for key in (
                "status", "events", "nodes", "edges", "myelinated_paths",
                "coactivation_paths", "consolidation_passes", "nodes_by_kind",
                "hubs", "fast_paths", "weak_paths", "last_consolidation",
            )
        },
        "autonomy": {
            key: autonomy.get(key)
            for key in (
                "status", "process_role", "auto_train_enabled", "ticks",
                "last_train_at", "last_train_status", "last_train_result",
                "self_study_enabled", "last_self_study_at",
                "last_self_study_result", "training_readiness",
            )
        },
        "adapter": adapter,
        "experience": experience,
        "grounded_in": [
            str(workspace / ".synapse" / "growth.sqlite3"),
            str(workspace / ".synapse" / "experience.sqlite3"),
            str(workspace / ".synapse" / "autonomy_state.json"),
            str(adapter.get("adapter_path") or ""),
        ],
        "protocol_version": PROTOCOL_VERSION,
    }


__all__ = ["execute_self_inspection"]
