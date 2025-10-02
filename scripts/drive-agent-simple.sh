#!/bin/bash
# Simple script to drive agent testing using curl commands

echo "🤖 Starting Agent Load Testing..."
echo "=================================="

# Test goals to cycle through
goals=(
    "test-login"
    "test-api"
    "test-data"
    "test-auth"
    "test-flow"
)

# Run for 5 minutes (300 seconds)
end_time=$(($(date +%s) + 300))
session_count=0

while [ $(date +%s) -lt $end_time ]; do
    # Pick a random goal
    goal=${goals[$RANDOM % ${#goals[@]}]}
    
    echo "📝 Creating session with goal: $goal"
    
    # Create session
    response=$(echo "{\"goal\":\"$goal\"}" | curl -s -X POST http://localhost:8000/sessions \
        -H "Content-Type: application/json" -d @-)
    
    if echo "$response" | grep -q "session_id"; then
        session_id=$(echo "$response" | grep -o '"session_id":"[^"]*"' | cut -d'"' -f4)
        echo "✅ Created session: $session_id"
        
        # Wait a bit
        sleep 2
        
        # Execute the session
        echo "🚀 Executing session: $session_id"
        exec_response=$(echo "{\"prompt\":\"Start testing the API endpoints\"}" | \
            curl -s -X POST "http://localhost:8000/sessions/$session_id/execute" \
            -H "Content-Type: application/json" -d @-)
        
        if echo "$exec_response" | grep -q "success\|response"; then
            echo "✅ Session executed successfully"
        else
            echo "❌ Session execution failed: $exec_response"
        fi
        
        session_count=$((session_count + 1))
        echo "📊 Completed session #$session_count"
        
    else
        echo "❌ Failed to create session: $response"
    fi
    
    # Wait before next session (5-15 seconds)
    sleep_time=$((5 + RANDOM % 10))
    echo "⏳ Waiting ${sleep_time}s before next session..."
    sleep $sleep_time
    
done

echo "✅ Load testing completed. Created $session_count sessions."