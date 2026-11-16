"""Task 1.8: run the real judge on one weak and one strong fictional answer.

Usage:
    uv run python scripts/judge_demo.py

Spends 2 model calls. Exit codes: 0 weak <= 2 and strong >= 4 with justifications,
1 expectation not met, 2 model call failed.
"""

import sys

from pydantic import ValidationError

from mia.judge import judge_answer
from mia.llm import LLMInvalidOutputError, ModelConfigError
from mia.schemas import AnswerScore, Question

QUESTION = Question(
    id="demo-q1",
    phase="technical",
    competency="Otimização de desempenho",
    text="Conte sobre uma vez em que você melhorou o desempenho de um sistema.",
    purpose="Avaliar capacidade de diagnosticar, agir e medir resultado.",
    look_for=["cita exemplo concreto", "mede resultado", "explica trade-off"],
    follow_ups=[],
)

WEAK_ANSWER = (
    "Eu sempre procuro melhorar o desempenho dos sistemas em que trabalho. "
    "Acho importante otimizar bem e seguir boas práticas, trabalhando em equipe."
)

STRONG_ANSWER = (
    "No projeto Catálogo, a busca levava 2 segundos por consulta. Medi com profiling e vi que "
    "o gargalo era a consulta repetida ao banco. Adicionei cache em memória com expiração de "
    "5 minutos e a latência caiu de 2s para 600ms, uma queda de 70%. O trade-off foi aceitar "
    "dados até 5 minutos desatualizados, o que o time de produto aprovou."
)


def run_case(label: str, answer: str) -> AnswerScore:
    score = judge_answer(QUESTION, answer, session_id="judge-demo")
    print(f"== {label}: nota {score.score}")
    print(f"critérios: {score.criteria_met}")
    print(f"citações: {score.evidence_quotes} (verificadas: {score.quotes_verified})")
    print(f"justificativa: {score.justification}\n")
    return score


def main() -> int:
    try:
        weak = run_case("Resposta fraca", WEAK_ANSWER)
        strong = run_case("Resposta forte", STRONG_ANSWER)
    except ValidationError:
        print("Falha na chamada ao modelo: configuração inválida.", file=sys.stderr)
        return 2
    except (LLMInvalidOutputError, ModelConfigError) as exc:
        print(f"Falha na chamada ao modelo: {exc}", file=sys.stderr)
        return 2
    ok = (
        weak.score <= 2
        and strong.score >= 4
        and bool(weak.justification.strip())
        and bool(strong.justification.strip())
    )
    print("OK: fraca <= 2 e forte >= 4" if ok else "FALHOU: notas fora do esperado")
    return 0 if ok else 1


if __name__ == "__main__":
    # Windows pipes default to cp1252: print accents as UTF-8.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    sys.exit(main())
