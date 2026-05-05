#!/bin/bash
# Complete end-to-end test of the Claims Processing API
# Tests both local and deployed versions

set -e

echo "╔══════════════════════════════════════════════════════════╗"
echo "║     Claims Processing API - End-to-End Test              ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEST_IMAGE="$SCRIPT_DIR/../challenge-0/data/statements/crash1_front.jpeg"
CURL_HEADERS=()

if [ -n "$APIM_BEARER_TOKEN" ]; then
    if [[ "$APIM_BEARER_TOKEN" =~ ^[Bb]earer\  ]]; then
        CURL_HEADERS+=(-H "Authorization: $APIM_BEARER_TOKEN")
    else
        CURL_HEADERS+=(-H "Authorization: Bearer $APIM_BEARER_TOKEN")
    fi
fi

if [ -n "$BEARER_TOKEN" ] && [ -z "$APIM_BEARER_TOKEN" ]; then
    if [[ "$BEARER_TOKEN" =~ ^[Bb]earer\  ]]; then
        CURL_HEADERS+=(-H "Authorization: $BEARER_TOKEN")
    else
        CURL_HEADERS+=(-H "Authorization: Bearer $BEARER_TOKEN")
    fi
fi

if [ ! -f "$TEST_IMAGE" ]; then
    echo "❌ Test image not found: $TEST_IMAGE"
    exit 1
fi

echo "📸 Test image: $TEST_IMAGE"
echo ""

test_api() {
    local API_URL=$1
    echo "🎯 Testing API at: $API_URL"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    echo ""
    echo "1️⃣ Testing health endpoint..."
    HEALTH_RESPONSE=$(curl -s "${CURL_HEADERS[@]}" "$API_URL/health")
    HEALTH_STATUS=$(echo $HEALTH_RESPONSE | jq -r '.status' 2>/dev/null || echo "error")

    if [ "$HEALTH_STATUS" = "healthy" ]; then
        echo "   ✅ Health check passed"
        echo "   Response: $HEALTH_RESPONSE" | head -c 100
        echo "..."
    else
        echo "   ❌ Health check failed"
        echo "   Response: $HEALTH_RESPONSE"
        return 1
    fi

    echo ""
    echo "2️⃣ Testing claim processing (file upload)..."
    echo "   Uploading image..."

    CLAIM_RESPONSE=$(curl -s -X POST "$API_URL/process-claim/upload" \
        "${CURL_HEADERS[@]}" \
        -F "file=@$TEST_IMAGE" \
        -w "\n%{http_code}")

    HTTP_CODE=$(echo "$CLAIM_RESPONSE" | tail -n 1)
    RESPONSE_BODY=$(echo "$CLAIM_RESPONSE" | head -n -1)

    if [ "$HTTP_CODE" = "200" ]; then
        SUCCESS=$(echo $RESPONSE_BODY | jq -r '.success' 2>/dev/null || echo "false")

        if [ "$SUCCESS" = "true" ]; then
            echo "   ✅ Claim processing succeeded"

            OCR_CHARS=$(echo $RESPONSE_BODY | jq -r '.data.metadata.ocr_characters' 2>/dev/null || echo "unknown")
            echo "   📊 OCR characters extracted: $OCR_CHARS"

            if echo $RESPONSE_BODY | jq -e '.data.vehicle_info' > /dev/null 2>&1; then
                echo "   🚗 Vehicle info detected:"
                echo $RESPONSE_BODY | jq '.data.vehicle_info' 2>/dev/null | sed 's/^/      /'
            fi

            TIMESTAMP=$(date +%Y%m%d_%H%M%S)
            OUTPUT_FILE="test_result_${TIMESTAMP}.json"
            echo $RESPONSE_BODY | jq '.' > "$OUTPUT_FILE" 2>/dev/null
            echo "   💾 Full response saved to: $OUTPUT_FILE"

        else
            echo "   ❌ Claim processing failed"
            ERROR=$(echo $RESPONSE_BODY | jq -r '.error' 2>/dev/null || echo "unknown")
            echo "   Error: $ERROR"
            return 1
        fi
    else
        echo "   ❌ HTTP error: $HTTP_CODE"
        echo "   Response: $RESPONSE_BODY"
        return 1
    fi

    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "✅ All tests passed for $API_URL"
    echo ""

    return 0
}

if [ $# -eq 0 ]; then
    echo "🏠 Testing LOCAL server (http://localhost:8080)"
    echo ""

    if ! curl -s "${CURL_HEADERS[@]}" http://localhost:8080/health > /dev/null 2>&1; then
        echo "❌ Local server not running at http://localhost:8080"
        echo ""
        echo "To start the server, run:"
        echo "  python api_server.py"
        echo ""
        exit 1
    fi

    test_api "http://localhost:8080"
else
    API_URL=$1
    API_URL=${API_URL%/}

    echo "☁️  Testing DEPLOYED server ($API_URL)"
    echo ""

    test_api "$API_URL"
fi

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║              ✅ END-TO-END TEST COMPLETE ✅              ║"
echo "╚══════════════════════════════════════════════════════════╝"
