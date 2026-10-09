# API Contract: plan-fact-ai-assistant

## 1. Внутренние Python-контракты

### 1.1 loader.load

```python
def load(
    plan_path: str | Path,
    fact_path: str | Path,
    *,
    plan_sheet: str | None = None,
    fact_sheet: str | None = None,
    encoding: str = "utf-8",
) -> pd.DataFrame:
    '''Returns DataFrame with columns:
      account: str, period: str, plan: float, fact: float, owner: str | None
    Raises: FileNotFoundError, ValueError'''
```

### 1.2 analyzer.compute

```python
def compute(
    df: pd.DataFrame,
    *,
    threshold_yellow: float = 0.05,
    threshold_red: float = 0.15,
    top_n: int = 10,
) -> pd.DataFrame:
    '''Returns: account, period, plan, fact, abs_variance, rel_variance, status, owner'''
```

### 1.3 rag.retrieve

```python
@dataclass
class Chunk:
    text: str
    source: str
    page: int | None
    clause: str | None
    score: float

def retrieve(query: str, *, k: int = 5, min_score: float = 0.75) -> list[Chunk]: ...
```

### 1.4 llm_agent.generate

```python
class Reference(BaseModel):
    source: str
    page: int | None
    clause: str | None
    quote: str

class ReportItem(BaseModel):
    account: str
    period: str
    abs_variance: float
    rel_variance: float | None
    hypotheses: list[str]
    references: list[Reference]
    questions: list[str]

class ReportJSON(BaseModel):
    summary: str
    items: list[ReportItem]
    meta: dict

def generate(variance_df: pd.DataFrame, chunks: list[Chunk]) -> ReportJSON: ...
```

## 2. Переменные окружения

| Переменная | Тип | Default | Описание |
|---|---|---|---|
| LLM_PROVIDER | openai\|ollama | openai | выбор провайдера |
| OPENAI_API_KEY | str | — | обязателен при openai |
| LLM_MODEL | str | gpt-4o-mini | модель |
| OLLAMA_BASE_URL | url | http://localhost:11434 | для ollama |
| VECTOR_STORE | chroma\|faiss | chroma | бэкенд |
| EMBEDDING_MODEL | str | text-embedding-3-small | модель эмбеддингов |
| TOP_K | int | 5 | retrieval |
| MIN_SCORE | float | 0.75 | порог similarity |

## 3. CLI (опционально)

```ash
python -m planfact.cli analyze --plan data/plan.xlsx --fact data/fact.xlsx --docs data/docs/ --out report.md
```

## 4. Формат входных файлов
- План: account, period, plan, owner?
- Факт: account, period, fact
- Объединение: по ключу (account, period).

## 5. Формат выходного отчёта
- report.md — markdown
- report.json — ReportJSON
- charts/*.html — Plotly

## 6. Версионирование
- Python-контракты — SemVer.
- Env-переменные — обратная совместимость обязательна.