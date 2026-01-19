# Test Coverage Improvement Plan: 54% → 80%+

## Current Coverage Analysis

From the test run, current coverage is **54.42%** with these gaps:

### Critical Gaps (0-30% coverage):
- `app/db/init_db.py` - **0%** (30 statements, 30 missed)
- `app/services/ingestion_worker.py` - **13%** (109 statements, 95 missed)
- `app/services/query_worker.py` - **22%** (158 statements, 124 missed)
- `app/services/scraper.py` - **13%** (142 statements, 123 missed)
- `app/services/llm_service.py` - **17%** (133 statements, 110 missed)
- `app/services/query_service.py` - **28%** (82 statements, 59 missed)

### Medium Gaps (55-70% coverage):
- `app/services/embeddings.py` - **59%** (61 statements, 25 missed)
- `app/services/vector_db.py` - **55%** (60 statements, 27 missed)
- `app/api/v1/routes/devices.py` - **71%** (69 statements, 20 missed)
- `app/api/v1/routes/queries.py` - **69%** (48 statements, 15 missed)
- `app/db/session.py` - **67%** (15 statements, 5 missed)
- `app/core/logging_config.py` - **82%** (40 statements, 7 missed)
- `app/main.py` - **85%** (119 statements, 18 missed)

## Strategy

Focus on the **critical gaps first** (0-30% coverage) as they have the most impact. These modules represent ~600+ uncovered statements. Improving these to 70%+ will significantly boost overall coverage.

## Implementation Plan

### Phase 1: Worker Functions (Highest Impact)
**Target**: `ingestion_worker.py` (13% → 70%) and `query_worker.py` (22% → 70%)

#### 1.1 Test `app/services/ingestion_worker.py`
**File**: `tests/test_ingestion_worker.py` (NEW)

Test cases:
- `test_process_ingestion_success` - Full happy path with mocked dependencies
- `test_process_ingestion_not_found` - Ingestion ID doesn't exist
- `test_process_ingestion_scraping_error` - Scraping fails
- `test_process_ingestion_truncation` - Text exceeds max_tokens, gets truncated
- `test_process_ingestion_empty_chunks` - No chunks generated
- `test_process_ingestion_embedding_failure` - Embedding generation fails
- `test_process_ingestion_vector_db_failure` - Vector DB storage fails
- `test_process_ingestion_with_db_session` - Passes existing session
- `test_process_ingestion_creates_new_session` - Creates new session when None
- `test_update_failed_status` - Helper function for error status updates

**Mocking Strategy**:
- Mock `fetch_html`, `extract_readable_content`, `chunk_text`, `generate_embeddings`, `store_chunks`
- Use real database session from test fixture
- Test error paths and edge cases

#### 1.2 Test `app/services/query_worker.py`
**File**: `tests/test_query_worker.py` (NEW)

Test cases:
- `test_process_query_success` - Full happy path
- `test_process_query_not_found` - Query ID doesn't exist
- `test_process_query_no_ingestion` - No successful ingestion for device
- `test_process_query_timeout` - Query exceeds timeout
- `test_process_query_no_chunks_found` - No relevant chunks found
- `test_process_query_embedding_failure` - Embedding generation fails
- `test_process_query_llm_failure` - LLM generation fails
- `test_process_query_quota_deduction` - Atomic quota deduction
- `test_process_query_with_db_session` - Passes existing session
- `test_update_failed_status` - Helper function for error status updates

**Mocking Strategy**:
- Mock `embed_query`, `search_relevant_chunks`, `assemble_context`, `generate_answer`
- Use real database session from test fixture
- Test error paths and edge cases

### Phase 2: Scraper Service (High Impact)
**Target**: `scraper.py` (13% → 70%)

#### 2.1 Test `app/services/scraper.py`
**File**: `tests/test_scraper.py` (NEW)

Test cases:
- `test_fetch_html_success` - Successful HTTP fetch
- `test_fetch_html_timeout` - Request timeout
- `test_fetch_html_http_error` - HTTP error responses (4xx, 5xx)
- `test_fetch_html_rate_limit` - 429 rate limit error
- `test_fetch_html_network_error` - Network errors
- `test_fetch_html_size_limit` - Response exceeds max size
- `test_extract_readable_content_beautifulsoup` - BeautifulSoup extraction
- `test_extract_readable_content_readability` - Readability-lxml extraction
- `test_extract_readable_content_fallback` - Fallback extraction
- `test_extract_readable_content_empty` - Empty content handling
- `test_truncate_text` - Text truncation logic
- `test_estimate_tokens` - Token estimation
- `test_get_browser_headers` - Header generation

**Mocking Strategy**:
- Mock `httpx.Client` for HTTP requests
- Use real HTML samples for extraction tests
- Test all extraction strategies

### Phase 3: LLM and Query Services (High Impact)
**Target**: `llm_service.py` (17% → 70%) and `query_service.py` (28% → 70%)

#### 3.1 Test `app/services/llm_service.py`
**File**: `tests/test_llm_service.py` (NEW)

Test cases:
- `test_get_client` - Client initialization
- `test_get_client_thread_safe` - Thread-safe singleton
- `test_check_circuit_breaker_closed` - Circuit breaker closed state
- `test_check_circuit_breaker_open` - Circuit breaker open state
- `test_check_circuit_breaker_reset` - Circuit breaker reset after timeout
- `test_record_circuit_breaker_success` - Success recording
- `test_record_circuit_breaker_failure` - Failure recording
- `test_generate_answer_success` - Successful answer generation
- `test_generate_answer_retry_on_rate_limit` - Rate limit retry
- `test_generate_answer_retry_on_api_error` - API error retry
- `test_generate_answer_circuit_breaker_open` - Fast-fail when circuit open
- `test_generate_answer_strict_mode` - Strict mode enforcement
- `test_generate_answer_timeout` - Request timeout handling

**Mocking Strategy**:
- Mock `OpenAI` client and `chat.completions.create`
- Test retry logic and circuit breaker

#### 3.2 Test `app/services/query_service.py` (Expand existing)
**File**: `tests/test_query_service.py` (EXPAND)

Additional test cases:
- `test_embed_query_success` - Successful embedding generation
- `test_embed_query_failure` - Embedding generation failure
- `test_search_relevant_chunks_success` - Successful chunk search
- `test_search_relevant_chunks_no_results` - No chunks found
- `test_search_relevant_chunks_filter_by_ingestion` - Ingestion ID filtering
- `test_search_relevant_chunks_similarity_threshold` - Similarity filtering
- `test_search_relevant_chunks_max_limit` - Max chunks limit
- `test_assemble_context_full_chunks` - Context assembly with full chunks
- `test_assemble_context_snippet_compression` - Snippet compression for low-relevance chunks
- `test_assemble_context_token_limit` - Token limit enforcement
- `test_assemble_context_empty_chunks` - Empty chunks handling

**Mocking Strategy**:
- Mock `generate_embeddings` and `get_collection`
- Test similarity calculations and filtering

### Phase 4: Embeddings and Vector DB (Medium Impact)
**Target**: `embeddings.py` (59% → 80%) and `vector_db.py` (55% → 80%)

#### 4.1 Test `app/services/embeddings.py` (Expand existing)
**File**: `tests/test_embeddings.py` (NEW)

Test cases:
- `test_get_client` - Client initialization
- `test_normalize_embedding_success` - Successful normalization
- `test_normalize_embedding_wrong_dimension` - Dimension mismatch error
- `test_normalize_embedding_zero_norm` - Zero-norm handling
- `test_generate_embeddings_success` - Successful generation
- `test_generate_embeddings_empty_list` - Empty input list
- `test_generate_embeddings_without_normalize` - Generation without normalization
- `test_generate_embeddings_retry_on_rate_limit` - Rate limit retry
- `test_generate_embeddings_retry_on_api_error` - API error retry
- `test_generate_embeddings_dimension_validation` - Dimension validation

**Mocking Strategy**:
- Mock `OpenAI` client and `embeddings.create`
- Test retry logic and normalization

#### 4.2 Test `app/services/vector_db.py` (Expand existing)
**File**: `tests/test_vector_db.py` (NEW)

Test cases:
- `test_get_client` - Client initialization
- `test_get_collection_existing` - Retrieve existing collection
- `test_get_collection_create_new` - Create new collection
- `test_get_collection_recreate_wrong_metric` - Recreate if wrong metric
- `test_store_chunks_success` - Successful chunk storage
- `test_store_chunks_mismatch_count` - Chunk/embedding count mismatch
- `test_store_chunks_dimension_mismatch` - Embedding dimension mismatch
- `test_store_chunks_storage_failure` - Storage failure handling

**Mocking Strategy**:
- Mock `chromadb.PersistentClient` and collection operations
- Use temporary directory for ChromaDB

### Phase 5: API Routes and Edge Cases (Medium Impact)
**Target**: Improve route coverage to 80%+

#### 5.1 Test `app/api/v1/routes/devices.py` (Expand existing)
**File**: `tests/test_api_devices.py` (EXPAND)

Additional test cases:
- `test_register_device_race_condition` - IntegrityError handling
- `test_register_device_existing_with_active_token` - Return existing token path
- `test_register_device_existing_no_active_token` - Create new token path (already fixed)

#### 5.2 Test `app/api/v1/routes/queries.py` (Expand existing)
**File**: `tests/test_api_queries.py` (EXPAND)

Additional test cases:
- `test_get_query_status_with_ingestion_url` - URL retrieval from ingestion
- `test_get_query_status_without_ingestion` - Missing ingestion handling
- `test_submit_query_atomic_quota_deduction` - Atomic quota check (already tested but verify)

### Phase 6: Database and Initialization (Low Impact but Easy)
**Target**: `init_db.py` (0% → 80%) and `session.py` (67% → 80%)

#### 6.1 Test `app/db/init_db.py`
**File**: `tests/test_init_db.py` (EXPAND)

Additional test cases:
- `test_init_db_creates_directory` - Directory creation for SQLite
- `test_init_db_handles_existing_tables` - Idempotent table creation
- `test_init_db_raises_on_failure` - Error handling
- `test_init_db_verifies_tables` - Table verification logic
- `test_init_db_cli_main` - CLI entry point

#### 6.2 Test `app/db/session.py`
**File**: `tests/test_session.py` (NEW)

Test cases:
- `test_get_db_yields_session` - Session yielding
- `test_get_db_closes_session` - Session cleanup
- `test_create_engine_sqlite` - SQLite engine creation
- `test_create_engine_postgres` - PostgreSQL engine creation (if applicable)

### Phase 7: Main App and Logging (Low Impact)
**Target**: `main.py` (85% → 90%) and `logging_config.py` (82% → 90%)

#### 7.1 Test `app/main.py` (Expand existing)
**File**: `tests/test_main.py` (EXPAND)

Additional test cases:
- `test_lifespan_startup_validation_failure` - Startup validation error
- `test_lifespan_db_init_failure` - Database init failure
- `test_lifespan_shutdown` - Shutdown logic
- `test_request_id_middleware` - Request ID generation

#### 7.2 Test `app/core/logging_config.py`
**File**: `tests/test_logging_config.py` (NEW)

Test cases:
- `test_setup_logging_development` - Development logging format
- `test_setup_logging_production` - Production JSON logging
- `test_setup_logging_test` - Test logging format

## Testing Strategy

### Mocking Approach
1. **External Services**: Mock OpenAI, ChromaDB, HTTP clients
2. **Database**: Use real SQLite in-memory/test files for integration tests
3. **Background Tasks**: Test worker functions directly with mocked dependencies
4. **Time-dependent**: Mock `time.time()` for timeout tests

### Test Organization
- **Unit Tests**: Test individual functions with mocked dependencies
- **Integration Tests**: Test API endpoints with real database
- **Worker Tests**: Test background workers with mocked external services

### Coverage Goals by Module
- **Critical modules** (workers, scraper): 70%+
- **Service modules** (embeddings, vector_db, query_service, llm_service): 80%+
- **API routes**: 80%+
- **Utilities** (init_db, session, logging): 80%+

## Estimated Impact

Improving these modules should add coverage for approximately:
- **Worker functions**: ~200 statements → +15-20% overall
- **Scraper**: ~100 statements → +7-10% overall
- **LLM/Query services**: ~150 statements → +10-12% overall
- **Embeddings/Vector DB**: ~50 statements → +3-4% overall
- **Routes/DB/Utils**: ~50 statements → +3-4% overall

**Total estimated improvement**: +38-50% → **Target: 80-85% overall coverage**

## Implementation Order

1. **Phase 1** (Workers) - Highest impact, most complex
2. **Phase 2** (Scraper) - High impact, moderate complexity
3. **Phase 3** (LLM/Query) - High impact, moderate complexity
4. **Phase 4** (Embeddings/Vector DB) - Medium impact, low complexity
5. **Phase 5** (Routes) - Medium impact, low complexity
6. **Phase 6** (DB/Init) - Low impact, very low complexity
7. **Phase 7** (Main/Logging) - Low impact, very low complexity

## Verification

After each phase:
1. Run `pytest tests/ -v --cov=app --cov-report=term-missing`
2. Check coverage percentage
3. Identify remaining gaps
4. Adjust plan if needed

## Notes

- Focus on **functional coverage** (testing code paths) not just line coverage
- Ensure tests are **maintainable** and **fast**
- Use **fixtures** for common setup (database, mocks)
- Test **error paths** and **edge cases**, not just happy paths
- Keep tests **isolated** - each test should be independent
