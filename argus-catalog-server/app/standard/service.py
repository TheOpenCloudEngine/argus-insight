"""데이터 표준 서비스 레이어.

표준 사전/단어/도메인/용어/코드 CRUD와 형태소 분석, 준수율 계산.
"""

import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.standard.models import (
    CodeGroup, CodeValue, StandardChangeLog, StandardDictionary,
    StandardDomain, StandardTerm, StandardTermWord, StandardWord,
    TermColumnMapping,
)
from app.standard.schemas import (
    AutoMapResult, CodeGroupCreate, CodeGroupResponse, CodeGroupUpdate,
    CodeValueCreate, CodeValueResponse, ColumnTermStatus, ComplianceStats,
    DatasetTermMapping, DictionaryCreate, DictionaryResponse, DictionaryUpdate,
    DomainCreate, DomainResponse, DomainUpdate, MorphemeResult, TermCreate,
    TermMappingCreate, TermMappingResponse, TermResponse, TermUpdate,
    TermWordInfo, WordCreate, WordResponse, WordUpdate,
)
from app.catalog.models import Dataset, DatasetSchema

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Dictionary CRUD
# ---------------------------------------------------------------------------

async def create_dictionary(session: AsyncSession, data: DictionaryCreate) -> DictionaryResponse:
    d = StandardDictionary(**data.model_dump())
    session.add(d)
    await session.flush()
    await session.refresh(d)
    return await _build_dict_response(session, d)


async def list_dictionaries(session: AsyncSession) -> list[DictionaryResponse]:
    rows = (await session.execute(
        select(StandardDictionary).order_by(StandardDictionary.dict_name)
    )).scalars().all()
    return [await _build_dict_response(session, d) for d in rows]


async def get_dictionary(session: AsyncSession, dict_id: int):
    return (await session.execute(
        select(StandardDictionary).where(StandardDictionary.id == dict_id)
    )).scalar_one_or_none()


async def update_dictionary(session: AsyncSession, dict_id: int, data: DictionaryUpdate):
    d = await get_dictionary(session, dict_id)
    if not d:
        return None
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(d, k, v)
    await session.flush()
    await session.refresh(d)
    return await _build_dict_response(session, d)


async def delete_dictionary(session: AsyncSession, dict_id: int) -> bool:
    d = await get_dictionary(session, dict_id)
    if not d:
        return False
    await session.delete(d)
    await session.flush()
    return True


async def _build_dict_response(session: AsyncSession, d: StandardDictionary) -> DictionaryResponse:
    wc = (await session.execute(select(func.count(StandardWord.id)).where(StandardWord.dictionary_id == d.id))).scalar() or 0
    dc = (await session.execute(select(func.count(StandardDomain.id)).where(StandardDomain.dictionary_id == d.id))).scalar() or 0
    tc = (await session.execute(select(func.count(StandardTerm.id)).where(StandardTerm.dictionary_id == d.id))).scalar() or 0
    cc = (await session.execute(select(func.count(CodeGroup.id)).where(CodeGroup.dictionary_id == d.id))).scalar() or 0
    return DictionaryResponse(
        id=d.id, dict_name=d.dict_name, description=d.description,
        version=d.version, status=d.status,
        effective_date=d.effective_date, expiry_date=d.expiry_date,
        created_by=d.created_by, created_at=d.created_at, updated_at=d.updated_at,
        word_count=wc, domain_count=dc, term_count=tc, code_group_count=cc,
    )


# ---------------------------------------------------------------------------
# Word CRUD
# ---------------------------------------------------------------------------

async def create_word(session: AsyncSession, data: WordCreate) -> WordResponse:
    w = StandardWord(**data.model_dump())
    session.add(w)
    await session.flush()
    await session.refresh(w)
    await _log_change(session, "WORD", w.id, "CREATE")
    return WordResponse.model_validate(w)


async def list_words(session: AsyncSession, dictionary_id: int, word_type: str | None = None) -> list[WordResponse]:
    stmt = select(StandardWord).where(StandardWord.dictionary_id == dictionary_id)
    if word_type:
        stmt = stmt.where(StandardWord.word_type == word_type)
    stmt = stmt.order_by(StandardWord.word_name)
    return [WordResponse.model_validate(w) for w in (await session.execute(stmt)).scalars().all()]


async def get_word(session: AsyncSession, word_id: int):
    return (await session.execute(select(StandardWord).where(StandardWord.id == word_id))).scalar_one_or_none()


async def update_word(session: AsyncSession, word_id: int, data: WordUpdate) -> WordResponse | None:
    w = await get_word(session, word_id)
    if not w:
        return None
    for k, v in data.model_dump(exclude_unset=True).items():
        old = getattr(w, k)
        if old != v:
            await _log_change(session, "WORD", w.id, "UPDATE", k, str(old), str(v))
        setattr(w, k, v)
    await session.flush()
    await session.refresh(w)
    return WordResponse.model_validate(w)


async def delete_word(session: AsyncSession, word_id: int) -> bool:
    w = await get_word(session, word_id)
    if not w:
        return False
    await _log_change(session, "WORD", w.id, "DELETE")
    await session.delete(w)
    await session.flush()
    return True


# ---------------------------------------------------------------------------
# Domain CRUD
# ---------------------------------------------------------------------------

async def create_domain(session: AsyncSession, data: DomainCreate) -> DomainResponse:
    d = StandardDomain(**data.model_dump())
    session.add(d)
    await session.flush()
    await session.refresh(d)
    await _log_change(session, "DOMAIN", d.id, "CREATE")
    return await _build_domain_response(session, d)


async def list_domains(session: AsyncSession, dictionary_id: int) -> list[DomainResponse]:
    rows = (await session.execute(
        select(StandardDomain).where(StandardDomain.dictionary_id == dictionary_id)
        .order_by(StandardDomain.domain_name)
    )).scalars().all()
    return [await _build_domain_response(session, d) for d in rows]


async def get_domain(session: AsyncSession, domain_id: int):
    return (await session.execute(select(StandardDomain).where(StandardDomain.id == domain_id))).scalar_one_or_none()


async def update_domain(session: AsyncSession, domain_id: int, data: DomainUpdate) -> DomainResponse | None:
    d = await get_domain(session, domain_id)
    if not d:
        return None
    for k, v in data.model_dump(exclude_unset=True).items():
        old = getattr(d, k)
        if old != v:
            await _log_change(session, "DOMAIN", d.id, "UPDATE", k, str(old), str(v))
        setattr(d, k, v)
    await session.flush()
    await session.refresh(d)
    return await _build_domain_response(session, d)


async def delete_domain(session: AsyncSession, domain_id: int) -> bool:
    d = await get_domain(session, domain_id)
    if not d:
        return False
    await _log_change(session, "DOMAIN", d.id, "DELETE")
    await session.delete(d)
    await session.flush()
    return True


async def _build_domain_response(session: AsyncSession, d: StandardDomain) -> DomainResponse:
    cg_name = None
    if d.code_group_id:
        cg = (await session.execute(select(CodeGroup.group_name).where(CodeGroup.id == d.code_group_id))).scalar_one_or_none()
        cg_name = cg
    return DomainResponse(
        id=d.id, dictionary_id=d.dictionary_id, domain_name=d.domain_name,
        domain_group=d.domain_group, data_type=d.data_type,
        data_length=d.data_length, data_precision=d.data_precision, data_scale=d.data_scale,
        description=d.description, code_group_id=d.code_group_id, code_group_name=cg_name,
        status=d.status, created_at=d.created_at, updated_at=d.updated_at,
    )


# ---------------------------------------------------------------------------
# Code Group / Value CRUD
# ---------------------------------------------------------------------------

async def create_code_group(session: AsyncSession, data: CodeGroupCreate) -> CodeGroupResponse:
    cg = CodeGroup(**data.model_dump())
    session.add(cg)
    await session.flush()
    await session.refresh(cg)
    await _log_change(session, "CODE_GROUP", cg.id, "CREATE")
    return await _build_code_group_response(session, cg)


async def list_code_groups(session: AsyncSession, dictionary_id: int) -> list[CodeGroupResponse]:
    rows = (await session.execute(
        select(CodeGroup).where(CodeGroup.dictionary_id == dictionary_id).order_by(CodeGroup.group_name)
    )).scalars().all()
    return [await _build_code_group_response(session, cg) for cg in rows]


async def get_code_group(session: AsyncSession, group_id: int):
    return (await session.execute(select(CodeGroup).where(CodeGroup.id == group_id))).scalar_one_or_none()


async def add_code_value(session: AsyncSession, group_id: int, data: CodeValueCreate) -> CodeValueResponse:
    cv = CodeValue(code_group_id=group_id, **data.model_dump())
    session.add(cv)
    await session.flush()
    await session.refresh(cv)
    return CodeValueResponse.model_validate(cv)


async def delete_code_value(session: AsyncSession, value_id: int) -> bool:
    cv = (await session.execute(select(CodeValue).where(CodeValue.id == value_id))).scalar_one_or_none()
    if not cv:
        return False
    await session.delete(cv)
    await session.flush()
    return True


async def _build_code_group_response(session: AsyncSession, cg: CodeGroup) -> CodeGroupResponse:
    values = (await session.execute(
        select(CodeValue).where(CodeValue.code_group_id == cg.id).order_by(CodeValue.sort_order)
    )).scalars().all()
    return CodeGroupResponse(
        id=cg.id, dictionary_id=cg.dictionary_id, group_name=cg.group_name,
        group_english=cg.group_english, description=cg.description,
        status=cg.status, created_at=cg.created_at, updated_at=cg.updated_at,
        values=[CodeValueResponse.model_validate(v) for v in values],
    )


# ---------------------------------------------------------------------------
# Term CRUD + 형태소 분석
# ---------------------------------------------------------------------------

async def analyze_term(session: AsyncSession, dictionary_id: int, term_name: str) -> MorphemeResult:
    """용어를 형태소 분석하여 단어 분해, 영문 약어, 도메인 추천 결과를 반환.

    탐욕적(greedy) 최장 매치 알고리즘으로 단어 사전에서 매칭.
    """
    words = (await session.execute(
        select(StandardWord)
        .where(StandardWord.dictionary_id == dictionary_id, StandardWord.status == "ACTIVE")
        .order_by(func.length(StandardWord.word_name).desc())
    )).scalars().all()

    word_map = {w.word_name: w for w in words}
    sorted_names = sorted(word_map.keys(), key=len, reverse=True)

    # 최장 매치 분해
    remaining = term_name
    matched_words: list[tuple[int, StandardWord]] = []
    unmatched: list[str] = []
    ordinal = 1

    while remaining:
        found = False
        for name in sorted_names:
            if remaining.startswith(name):
                w = word_map[name]
                matched_words.append((ordinal, w))
                remaining = remaining[len(name):]
                ordinal += 1
                found = True
                break
        if not found:
            unmatched.append(remaining[0])
            remaining = remaining[1:]

    # 자동 생성
    term_english = " ".join(w.word_english for _, w in matched_words)
    term_abbr = "_".join(w.word_abbr for _, w in matched_words)
    physical_name = term_abbr.lower()

    # SUFFIX 단어 기반 도메인 추천
    recommended_domain = None
    suffix_words = [w for _, w in matched_words if w.word_type == "SUFFIX"]
    if suffix_words:
        last_suffix = suffix_words[-1]
        domain = (await session.execute(
            select(StandardDomain)
            .where(
                StandardDomain.dictionary_id == dictionary_id,
                StandardDomain.domain_name == last_suffix.word_name,
                StandardDomain.status == "ACTIVE",
            )
        )).scalar_one_or_none()
        if domain:
            recommended_domain = await _build_domain_response(session, domain)

    word_infos = [
        TermWordInfo(
            word_id=w.id, word_name=w.word_name, word_english=w.word_english,
            word_abbr=w.word_abbr, word_type=w.word_type, ordinal=o,
        )
        for o, w in matched_words
    ]

    return MorphemeResult(
        words=word_infos,
        term_english=term_english or term_name,
        term_abbr=term_abbr or term_name.upper(),
        physical_name=physical_name or term_name.lower(),
        recommended_domain=recommended_domain,
        unmatched_parts=unmatched,
    )


async def create_term(session: AsyncSession, data: TermCreate) -> TermResponse:
    """용어 생성. 영문명/약어/물리명이 없으면 형태소 분석으로 자동 생성."""
    # 자동 생성 필요 시 형태소 분석
    if not data.term_english or not data.term_abbr or not data.physical_name:
        analysis = await analyze_term(session, data.dictionary_id, data.term_name)
        term_english = data.term_english or analysis.term_english
        term_abbr = data.term_abbr or analysis.term_abbr
        physical_name = data.physical_name or analysis.physical_name
        domain_id = data.domain_id
        if not domain_id and analysis.recommended_domain:
            domain_id = analysis.recommended_domain.id
        word_infos = analysis.words
    else:
        term_english = data.term_english
        term_abbr = data.term_abbr
        physical_name = data.physical_name
        domain_id = data.domain_id
        word_infos = []

    t = StandardTerm(
        dictionary_id=data.dictionary_id,
        term_name=data.term_name,
        term_english=term_english,
        term_abbr=term_abbr,
        physical_name=physical_name,
        domain_id=domain_id,
        description=data.description,
        created_by=data.created_by,
    )
    session.add(t)
    await session.flush()
    await session.refresh(t)

    # 단어 연결
    for wi in word_infos:
        tw = StandardTermWord(term_id=t.id, word_id=wi.word_id, ordinal=wi.ordinal)
        session.add(tw)
    await session.flush()

    await _log_change(session, "TERM", t.id, "CREATE")
    return await _build_term_response(session, t)


async def list_terms(session: AsyncSession, dictionary_id: int, search: str | None = None) -> list[TermResponse]:
    stmt = select(StandardTerm).where(StandardTerm.dictionary_id == dictionary_id)
    if search:
        stmt = stmt.where(StandardTerm.term_name.ilike(f"%{search}%"))
    stmt = stmt.order_by(StandardTerm.term_name)
    rows = (await session.execute(stmt)).scalars().all()
    return [await _build_term_response(session, t) for t in rows]


async def get_term(session: AsyncSession, term_id: int):
    return (await session.execute(select(StandardTerm).where(StandardTerm.id == term_id))).scalar_one_or_none()


async def update_term(session: AsyncSession, term_id: int, data: TermUpdate) -> TermResponse | None:
    t = await get_term(session, term_id)
    if not t:
        return None
    for k, v in data.model_dump(exclude_unset=True).items():
        old = getattr(t, k)
        if old != v:
            await _log_change(session, "TERM", t.id, "UPDATE", k, str(old), str(v))
        setattr(t, k, v)
    await session.flush()
    await session.refresh(t)
    return await _build_term_response(session, t)


async def delete_term(session: AsyncSession, term_id: int) -> bool:
    t = await get_term(session, term_id)
    if not t:
        return False
    await _log_change(session, "TERM", t.id, "DELETE")
    await session.delete(t)
    await session.flush()
    return True


async def _build_term_response(session: AsyncSession, t: StandardTerm) -> TermResponse:
    # 도메인 정보
    domain_name = domain_data_type = None
    if t.domain_id:
        d = await get_domain(session, t.domain_id)
        if d:
            domain_name = d.domain_name
            domain_data_type = d.data_type

    # 구성 단어
    tw_rows = (await session.execute(
        select(StandardTermWord, StandardWord)
        .join(StandardWord, StandardTermWord.word_id == StandardWord.id)
        .where(StandardTermWord.term_id == t.id)
        .order_by(StandardTermWord.ordinal)
    )).all()
    word_list = [
        TermWordInfo(
            word_id=w.id, word_name=w.word_name, word_english=w.word_english,
            word_abbr=w.word_abbr, word_type=w.word_type, ordinal=tw.ordinal,
        )
        for tw, w in tw_rows
    ]

    # 매핑 수
    mc = (await session.execute(
        select(func.count(TermColumnMapping.id)).where(TermColumnMapping.term_id == t.id)
    )).scalar() or 0

    return TermResponse(
        id=t.id, dictionary_id=t.dictionary_id, term_name=t.term_name,
        term_english=t.term_english, term_abbr=t.term_abbr, physical_name=t.physical_name,
        domain_id=t.domain_id, domain_name=domain_name, domain_data_type=domain_data_type,
        description=t.description, status=t.status, created_by=t.created_by,
        created_at=t.created_at, updated_at=t.updated_at, words=word_list, mapping_count=mc,
    )


# ---------------------------------------------------------------------------
# Term-Column Mapping
# ---------------------------------------------------------------------------

async def create_term_mapping(session: AsyncSession, data: TermMappingCreate) -> TermMappingResponse:
    m = TermColumnMapping(**data.model_dump())
    session.add(m)
    await session.flush()
    await session.refresh(m)
    return await _build_mapping_response(session, m)


async def list_term_mappings(
    session: AsyncSession, term_id: int | None = None, dataset_id: int | None = None,
) -> list[TermMappingResponse]:
    stmt = select(TermColumnMapping)
    if term_id:
        stmt = stmt.where(TermColumnMapping.term_id == term_id)
    if dataset_id:
        stmt = stmt.where(TermColumnMapping.dataset_id == dataset_id)
    rows = (await session.execute(stmt)).scalars().all()
    return [await _build_mapping_response(session, m) for m in rows]


async def delete_term_mapping(session: AsyncSession, mapping_id: int) -> bool:
    m = (await session.execute(select(TermColumnMapping).where(TermColumnMapping.id == mapping_id))).scalar_one_or_none()
    if not m:
        return False
    await session.delete(m)
    await session.flush()
    return True


async def _build_mapping_response(session: AsyncSession, m: TermColumnMapping) -> TermMappingResponse:
    term_name = (await session.execute(select(StandardTerm.term_name).where(StandardTerm.id == m.term_id))).scalar_one_or_none()
    ds_name = (await session.execute(select(Dataset.name).where(Dataset.id == m.dataset_id))).scalar_one_or_none()
    col_name = (await session.execute(select(DatasetSchema.field_path).where(DatasetSchema.id == m.schema_id))).scalar_one_or_none()
    return TermMappingResponse(
        id=m.id, term_id=m.term_id, term_name=term_name,
        dataset_id=m.dataset_id, dataset_name=ds_name,
        schema_id=m.schema_id, column_name=col_name,
        mapping_type=m.mapping_type, created_at=m.created_at,
    )


# ---------------------------------------------------------------------------
# Compliance (표준 준수율)
# ---------------------------------------------------------------------------

async def get_compliance_stats(
    session: AsyncSession, dictionary_id: int, dataset_id: int | None = None,
) -> ComplianceStats:
    """표준 준수율을 계산한다."""
    # 전체 컬럼 수
    col_stmt = select(func.count(DatasetSchema.id))
    if dataset_id:
        col_stmt = col_stmt.where(DatasetSchema.dataset_id == dataset_id)
    total = (await session.execute(col_stmt)).scalar() or 0

    if total == 0:
        return ComplianceStats()

    # 매핑된 컬럼 수 (by type)
    map_stmt = (
        select(TermColumnMapping.mapping_type, func.count(TermColumnMapping.id))
        .join(StandardTerm, TermColumnMapping.term_id == StandardTerm.id)
        .where(StandardTerm.dictionary_id == dictionary_id)
    )
    if dataset_id:
        map_stmt = map_stmt.where(TermColumnMapping.dataset_id == dataset_id)
    map_stmt = map_stmt.group_by(TermColumnMapping.mapping_type)

    rows = (await session.execute(map_stmt)).all()
    matched = similar = violation = 0
    for mt, cnt in rows:
        if mt == "MATCHED":
            matched = cnt
        elif mt == "SIMILAR":
            similar = cnt
        elif mt == "VIOLATION":
            violation = cnt

    mapped_total = matched + similar + violation
    unmapped = total - mapped_total
    rate = (matched / total * 100) if total > 0 else 0.0

    return ComplianceStats(
        total_columns=total, matched=matched, similar=similar,
        violation=violation, unmapped=unmapped, compliance_rate=round(rate, 1),
    )


# ---------------------------------------------------------------------------
# Auto-mapping (자동 매핑)
# ---------------------------------------------------------------------------

async def auto_map_dataset(
    session: AsyncSession, dictionary_id: int, dataset_id: int,
) -> AutoMapResult:
    """데이터셋의 컬럼을 표준 용어와 자동 매핑한다.

    매핑 로직:
    1. 컬럼의 field_path와 용어의 physical_name을 비교 (소문자 정규화)
    2. 정확히 일치하면:
       - 데이터 타입도 호환 → MATCHED
       - 데이터 타입 불일치 → VIOLATION
    3. 이미 매핑이 있으면 업데이트, 없으면 새로 생성
    """
    # 데이터셋의 모든 컬럼 조회
    columns = (await session.execute(
        select(DatasetSchema).where(DatasetSchema.dataset_id == dataset_id)
    )).scalars().all()

    # 사전의 모든 활성 용어 조회 (physical_name → term 맵)
    terms = (await session.execute(
        select(StandardTerm).where(
            StandardTerm.dictionary_id == dictionary_id,
            StandardTerm.status == "ACTIVE",
        )
    )).scalars().all()
    term_by_physical = {t.physical_name.lower(): t for t in terms}

    # 용어별 도메인 정보 캐시
    domain_cache: dict[int, StandardDomain | None] = {}
    for t in terms:
        if t.domain_id and t.domain_id not in domain_cache:
            domain_cache[t.domain_id] = (await session.execute(
                select(StandardDomain).where(StandardDomain.id == t.domain_id)
            )).scalar_one_or_none()

    # 기존 매핑 조회
    existing_mappings = (await session.execute(
        select(TermColumnMapping).where(TermColumnMapping.dataset_id == dataset_id)
    )).scalars().all()
    existing_by_schema = {m.schema_id: m for m in existing_mappings}

    result = AutoMapResult()

    for col in columns:
        col_name = col.field_path.lower()
        term = term_by_physical.get(col_name)

        if not term:
            result.unmapped += 1
            continue

        # 타입 호환성 확인
        mapping_type = "MATCHED"
        if term.domain_id:
            domain = domain_cache.get(term.domain_id)
            if domain:
                if not _types_compatible(col.field_type, col.native_type, domain):
                    mapping_type = "VIOLATION"

        if col.id in existing_by_schema:
            # 기존 매핑 업데이트
            existing = existing_by_schema[col.id]
            if existing.term_id != term.id or existing.mapping_type != mapping_type:
                existing.term_id = term.id
                existing.mapping_type = mapping_type
                result.updated += 1
        else:
            # 새 매핑 생성
            m = TermColumnMapping(
                term_id=term.id,
                dataset_id=dataset_id,
                schema_id=col.id,
                mapping_type=mapping_type,
            )
            session.add(m)
            result.created += 1

        if mapping_type == "MATCHED":
            result.matched += 1
        elif mapping_type == "VIOLATION":
            result.violation += 1

    await session.flush()
    return result


def _types_compatible(
    col_type: str | None, native_type: str | None, domain: StandardDomain,
) -> bool:
    """컬럼 타입과 도메인 타입이 호환되는지 확인."""
    if not col_type:
        return True

    ct = (col_type or "").upper()
    dt = domain.data_type.upper()

    # 직접 일치
    if ct == dt:
        return True

    # 호환 그룹
    varchar_types = {"VARCHAR", "CHAR", "CHARACTER VARYING", "STRING", "TEXT", "NVARCHAR"}
    int_types = {"INT", "INTEGER", "BIGINT", "SMALLINT", "TINYINT", "NUMBER"}
    decimal_types = {"DECIMAL", "NUMERIC", "FLOAT", "DOUBLE", "REAL", "DOUBLE PRECISION"}
    date_types = {"DATE", "TIMESTAMP", "DATETIME", "TIMESTAMPTZ", "TIMESTAMP WITH TIME ZONE"}

    for group in [varchar_types, int_types, decimal_types, date_types]:
        if ct in group and dt in group:
            return True

    return False


async def get_dataset_term_mapping(
    session: AsyncSession, dictionary_id: int, dataset_id: int,
) -> DatasetTermMapping:
    """데이터셋의 전체 컬럼-용어 매핑 현황을 조회한다."""
    columns = (await session.execute(
        select(DatasetSchema).where(DatasetSchema.dataset_id == dataset_id)
        .order_by(DatasetSchema.ordinal)
    )).scalars().all()

    # 이 데이터셋의 매핑 조회
    mappings = (await session.execute(
        select(TermColumnMapping)
        .join(StandardTerm, TermColumnMapping.term_id == StandardTerm.id)
        .where(
            TermColumnMapping.dataset_id == dataset_id,
            StandardTerm.dictionary_id == dictionary_id,
        )
    )).scalars().all()
    mapping_by_schema = {m.schema_id: m for m in mappings}

    # 용어 정보 캐시
    term_cache: dict[int, StandardTerm] = {}
    domain_cache: dict[int, StandardDomain | None] = {}
    for m in mappings:
        if m.term_id not in term_cache:
            t = (await session.execute(
                select(StandardTerm).where(StandardTerm.id == m.term_id)
            )).scalar_one_or_none()
            if t:
                term_cache[m.term_id] = t
                if t.domain_id and t.domain_id not in domain_cache:
                    domain_cache[t.domain_id] = (await session.execute(
                        select(StandardDomain).where(StandardDomain.id == t.domain_id)
                    )).scalar_one_or_none()

    col_statuses: list[ColumnTermStatus] = []
    matched = similar = violation = 0

    for col in columns:
        m = mapping_by_schema.get(col.id)
        if m and m.term_id in term_cache:
            term = term_cache[m.term_id]
            domain = domain_cache.get(term.domain_id) if term.domain_id else None
            col_statuses.append(ColumnTermStatus(
                schema_id=col.id,
                column_name=col.field_path,
                column_type=col.field_type,
                native_type=col.native_type,
                mapping_id=m.id,
                mapping_type=m.mapping_type,
                term_id=term.id,
                term_name=term.term_name,
                term_physical_name=term.physical_name,
                term_data_type=domain.data_type if domain else None,
                term_data_length=domain.data_length if domain else None,
            ))
            if m.mapping_type == "MATCHED":
                matched += 1
            elif m.mapping_type == "SIMILAR":
                similar += 1
            elif m.mapping_type == "VIOLATION":
                violation += 1
        else:
            col_statuses.append(ColumnTermStatus(
                schema_id=col.id,
                column_name=col.field_path,
                column_type=col.field_type,
                native_type=col.native_type,
            ))

    total = len(columns)
    unmapped = total - matched - similar - violation
    rate = (matched / total * 100) if total > 0 else 0.0

    return DatasetTermMapping(
        dataset_id=dataset_id,
        dictionary_id=dictionary_id,
        columns=col_statuses,
        compliance=ComplianceStats(
            total_columns=total, matched=matched, similar=similar,
            violation=violation, unmapped=unmapped, compliance_rate=round(rate, 1),
        ),
    )


# ---------------------------------------------------------------------------
# Change Log
# ---------------------------------------------------------------------------

async def _log_change(
    session: AsyncSession,
    entity_type: str, entity_id: int, change_type: str,
    field_name: str | None = None, old_value: str | None = None, new_value: str | None = None,
) -> None:
    log = StandardChangeLog(
        entity_type=entity_type, entity_id=entity_id, change_type=change_type,
        field_name=field_name, old_value=old_value, new_value=new_value,
    )
    session.add(log)


async def list_change_logs(
    session: AsyncSession, entity_type: str | None = None, entity_id: int | None = None,
    page: int = 1, page_size: int = 50,
) -> list[dict]:
    stmt = select(StandardChangeLog)
    if entity_type:
        stmt = stmt.where(StandardChangeLog.entity_type == entity_type)
    if entity_id:
        stmt = stmt.where(StandardChangeLog.entity_id == entity_id)
    stmt = stmt.order_by(StandardChangeLog.changed_at.desc()).offset((page - 1) * page_size).limit(page_size)
    rows = (await session.execute(stmt)).scalars().all()
    return [
        {
            "id": r.id, "entity_type": r.entity_type, "entity_id": r.entity_id,
            "change_type": r.change_type, "field_name": r.field_name,
            "old_value": r.old_value, "new_value": r.new_value,
            "changed_by": r.changed_by, "changed_at": r.changed_at.isoformat() if r.changed_at else None,
        }
        for r in rows
    ]
