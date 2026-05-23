"""
GraphRAG Backend API Test Suite - Fast Tests
Tests all non-Ollama endpoints quickly.
"""
import json
import sys
import time
import urllib.request
import urllib.error

BASE_URL = "http://localhost:8000"
PASS = 0
FAIL = 0
TOTAL = 0
ERRORS = []


def test(name, method="GET", path="/", expected_status=200, data=None, validate=None, timeout=15):
    global PASS, FAIL, TOTAL
    TOTAL += 1
    url = f"{BASE_URL}{path}"
    try:
        req_data = json.dumps(data).encode() if data else None
        req = urllib.request.Request(
            url,
            data=req_data,
            method=method,
            headers={"Content-Type": "application/json"} if data else {},
        )
        start = time.time()
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            elapsed = round((time.time() - start) * 1000, 1)
            status = resp.status
            body = resp.read().decode()
            try:
                result = json.loads(body)
            except json.JSONDecodeError:
                result = body

            if status != expected_status:
                FAIL += 1
                msg = f"[FAIL] {method} {path} - Expected {expected_status}, got {status} ({elapsed}ms)"
                ERRORS.append(msg)
                print(f"  [FAIL] {method} {path} - Expected {expected_status}, got {status} ({elapsed}ms)")
                return None

            if validate and not validate(result):
                FAIL += 1
                msg = f"[FAIL] {method} {path} - Validation failed. Response: {json.dumps(result, indent=2)[:200]}"
                ERRORS.append(msg)
                print(f"  [FAIL] {method} {path} - Validation failed ({elapsed}ms)")
                return None

            PASS += 1
            print(f"  [PASS] {method} {path} ({elapsed}ms)")
            return result
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        FAIL += 1
        msg = f"[FAIL] {method} {path} - HTTP {e.code}: {body[:200]}"
        ERRORS.append(msg)
        print(f"  [FAIL] {method} {path} - HTTP {e.code} ({body[:100]})")
        return None
    except Exception as e:
        FAIL += 1
        msg = f"[FAIL] {method} {path} - Exception: {str(e)}"
        ERRORS.append(msg)
        print(f"  [FAIL] {method} {path} - Exception: {str(e)}")
        return None


def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def main():
    global PASS, FAIL, TOTAL, ERRORS

    print("\n")
    print("  +------------------------------------------+")
    print("  |  GraphRAG Backend API Test Suite          |")
    print("  +------------------------------------------+")
    print(f"\n")
    print(f"  Target: {BASE_URL}")
    print(f"  Time:   {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # ── 1. Health & Info ──
    section("1. Health & Info Endpoints")
    test("Root endpoint", "GET", "/", 200, validate=lambda r: r.get("status") == "running")
    test("Health check", "GET", "/api/health", 200, validate=lambda r: r.get("status") == "healthy")
    test("App info", "GET", "/api/info", 200, validate=lambda r: "features" in r and isinstance(r["features"], list))

    # ── 2. Data Sources CRUD ──
    section("2. Data Source Endpoints")
    ds_result = test("Create datasource", "POST", "/api/datasources", 200,
                     data={"name": "Test CSV", "source_type": "csv", "config": {"path": "test.csv"}},
                     validate=lambda r: r.get("id") is not None)
    ds_id = ds_result.get("id") if ds_result else None

    test("List datasources", "GET", "/api/datasources", 200,
         validate=lambda r: isinstance(r, list))

    if ds_id:
        test("Get single datasource", "GET", f"/api/datasources/{ds_id}", 200,
             validate=lambda r: r.get("id") == ds_id)
        test("Delete datasource", "DELETE", f"/api/datasources/{ds_id}", 200,
             validate=lambda r: "message" in r)
        test("Get deleted datasource (404)", "GET", f"/api/datasources/{ds_id}", 404)
    test("Get nonexistent datasource (404)", "GET", "/api/datasources/9999", 404)

    # ── 3. Pipeline Endpoints ──
    section("3. Pipeline Endpoints")
    ds_for_pipeline = test("Create pipeline datasource", "POST", "/api/datasources", 200,
                           data={"name": "Pipeline Source", "source_type": "sqlite"})
    pipeline_ds_id = ds_for_pipeline.get("id") if ds_for_pipeline else 1

    pipeline_result = test("Create pipeline", "POST", "/api/pipelines", 200,
                           data={"data_source_id": pipeline_ds_id, "name": "Test Pipeline"},
                           validate=lambda r: r.get("id") is not None)
    pipeline_id = pipeline_result.get("id") if pipeline_result else None

    test("List pipelines", "GET", "/api/pipelines", 200, validate=lambda r: isinstance(r, list))

    if pipeline_id:
        test("Get single pipeline", "GET", f"/api/pipelines/{pipeline_id}", 200,
             validate=lambda r: r.get("id") == pipeline_id)
        test("Run pipeline", "POST", f"/api/pipelines/{pipeline_id}/run", 200,
             validate=lambda r: "message" in r)

    test("Get nonexistent pipeline (404)", "GET", "/api/pipelines/9999", 404)

    # ── 4. Graph Endpoints ──
    section("4. Graph Endpoints")
    test("Get graph", "GET", "/api/graph?limit=100", 200,
         validate=lambda r: isinstance(r.get("nodes"), list) and isinstance(r.get("edges"), list))
    test("Get graph stats", "GET", "/api/graph/stats", 200, validate=lambda r: isinstance(r, dict))
    test("Execute cypher - empty query (400)", "POST", "/api/graph/cypher", 400, data={"query": ""})
    test("Execute cypher", "POST", "/api/graph/cypher", 200,
         data={"query": "MATCH (n) RETURN n LIMIT 5"},
         validate=lambda r: isinstance(r.get("results"), list))

    # ── 5. Ollama Endpoints ──
    section("5. Ollama Endpoints")
    ollama_status = test("Get Ollama status", "GET", "/api/ollama/status", 200,
                         validate=lambda r: "available" in r)
    ollama_available = ollama_status.get("available", False) if ollama_status else False

    models_result = test("List Ollama models", "GET", "/api/ollama/models", 200,
                         validate=lambda r: isinstance(r, list))

    if models_result:
        model_names = [m['name'] for m in models_result]
        print(f"    -> Found {len(models_result)} model(s): {model_names}")

    test("Select model", "POST", "/api/ollama/models/select", 200,
         data={"model_name": "llama3.1"},
         validate=lambda r: "message" in r and "selected" in r["message"])

    if ollama_available:
        test("Pull model request", "POST", "/api/ollama/pull", 200,
             data={"model_name": "llama3.1:latest"},
             validate=lambda r: "message" in r and "Pulling" in r["message"])

    # ── 6. Query Endpoints (non-Ollama parts) ──
    section("6. Query Endpoints")
    test("Get query history", "GET", "/api/query/history?limit=10", 200,
         validate=lambda r: isinstance(r, list))
    test("Get query history - no limit", "GET", "/api/query/history", 200,
         validate=lambda r: isinstance(r, list))

    # ── 7. Dashboard Endpoints ──
    section("7. Dashboard Endpoints")
    metrics = test("Get system metrics", "GET", "/api/dashboard/metrics", 200,
                   validate=lambda r: all(k in r for k in ["cpu_usage", "ram_usage", "ram_total"]))
    if metrics:
        print(f"    -> CPU: {metrics['cpu_usage']}% | RAM: {metrics['ram_usage']}% ({metrics['ram_total']}GB)")

    health = test("Get dashboard health", "GET", "/api/dashboard/health", 200,
                  validate=lambda r: all(k in r for k in ["backend", "neo4j", "ollama"]))
    if health:
        print(f"    -> Backend: {health['backend']} | Neo4j: {health['neo4j']} | Ollama: {health['ollama']}")

    # ── 8. Seed Data ──
    section("8. Seed Data Endpoint")
    seed_result = test("Seed demo data", "POST", "/api/seed", 200, timeout=30,
                       validate=lambda r: "message" in r)
    if seed_result:
        print(f"    -> {seed_result.get('message', '')} | Nodes: {seed_result.get('nodes_created', 'N/A')}")

    # ── 9. Edge Cases & Error Handling ──
    section("9. Edge Cases & Error Handling")
    ds_for_delete = test("Create ds for delete test", "POST", "/api/datasources", 200,
                         data={"name": "Delete Me", "source_type": "csv"})
    delete_id = ds_for_delete.get("id") if ds_for_delete else None
    if delete_id:
        test("Delete datasource", "DELETE", f"/api/datasources/{delete_id}", 200)
        test("Delete already deleted (404)", "DELETE", f"/api/datasources/{delete_id}", 404)

    test("Cypher with invalid query", "POST", "/api/graph/cypher", 200,
         data={"query": "INVALID CYPHER QUERY"})

    # Check if response time field is present on all endpoints
    section("10. Response Time Compliance")
    test("Health check response time", "GET", "/api/health", 200, timeout=5)

    # ── Summary ──
    section("TEST RESULTS SUMMARY")
    pass_pct = round((PASS / TOTAL) * 100, 1) if TOTAL > 0 else 0
    print(f"  Passed: {PASS}/{TOTAL} ({pass_pct}%)")
    print(f"  Failed: {FAIL}/{TOTAL}")
    if FAIL > 0:
        print(f"\n  Defects Found:")
        for i, err in enumerate(ERRORS, 1):
            print(f"  {i}. {err}")
        return 1
    else:
        print(f"\n  All tests passed! No defects found.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
