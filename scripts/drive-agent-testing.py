#!/usr/bin/env python3
"""
Drive agent testing by continuously creating sessions and executing goals.
This script makes the agent actually test APIs instead of just sitting idle.
"""
import asyncio
import aiohttp
import json
import time
import random
from typing import List, Dict

class AgentDriver:
    def __init__(self, agent_url: str = "http://localhost:8000"):
        self.agent_url = agent_url
        self.active_sessions: List[str] = []
        
    async def create_session(self, goal: str) -> str:
        """Create a new agent session."""
        async with aiohttp.ClientSession() as session:
            payload = {"goal": goal}
            async with session.post(
                f"{self.agent_url}/sessions",
                json=payload,
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    session_id = data.get("session_id")
                    if session_id:
                        self.active_sessions.append(session_id)
                        print(f"✅ Created session: {session_id} with goal: {goal}")
                        return session_id
                else:
                    print(f"❌ Failed to create session: {response.status}")
                    return None
    
    async def execute_session(self, session_id: str, prompt: str = None) -> bool:
        """Execute a goal for a session."""
        async with aiohttp.ClientSession() as session:
            payload = {"prompt": prompt} if prompt else {}
            async with session.post(
                f"{self.agent_url}/sessions/{session_id}/execute",
                json=payload,
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"🚀 Executed session {session_id}: {data.get('success', 'unknown')}")
                    return True
                else:
                    error_text = await response.text()
                    print(f"❌ Failed to execute session {session_id}: {response.status} - {error_text}")
                    return False
    
    async def get_session_status(self, session_id: str) -> Dict:
        """Get session status."""
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.agent_url}/sessions/{session_id}") as response:
                if response.status == 200:
                    return await response.json()
                else:
                    return {"error": f"Status {response.status}"}
    
    async def run_continuous_testing(self, duration_minutes: int = 5):
        """Run continuous testing for specified duration."""
        print(f"🎯 Starting continuous agent testing for {duration_minutes} minutes...")
        
        goals = [
            "Test user login and profile access",
            "Complete e-commerce checkout flow", 
            "Validate API authentication endpoints",
            "Test data retrieval and updates",
            "Verify error handling and recovery"
        ]
        
        end_time = time.time() + (duration_minutes * 60)
        session_count = 0
        
        while time.time() < end_time:
            try:
                # Create a new session with random goal
                goal = random.choice(goals)
                session_id = await self.create_session(goal)
                
                if session_id:
                    session_count += 1
                    
                    # Wait a bit then execute the session
                    await asyncio.sleep(2)
                    
                    # Execute with a specific prompt
                    prompts = [
                        "Start by checking the health endpoint",
                        "Begin with user authentication flow",
                        "Test the main API endpoints",
                        "Validate data operations",
                        "Check error responses"
                    ]
                    prompt = random.choice(prompts)
                    
                    success = await self.execute_session(session_id, prompt)
                    
                    if success:
                        print(f"📊 Session {session_count} completed successfully")
                    
                    # Wait before next session
                    await asyncio.sleep(random.uniform(5, 15))
                
            except Exception as e:
                print(f"❌ Error in testing loop: {e}")
                await asyncio.sleep(5)
        
        print(f"✅ Completed continuous testing. Created {session_count} sessions.")

async def main():
    """Main function."""
    print("🤖 Agent Load Testing Driver")
    print("=" * 40)
    
    # Check if agent is accessible
    driver = AgentDriver()
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{driver.agent_url}/health") as response:
                if response.status == 200:
                    print("✅ Agent is accessible and healthy")
                else:
                    print(f"❌ Agent health check failed: {response.status}")
                    return
    except Exception as e:
        print(f"❌ Cannot connect to agent: {e}")
        print("Make sure the agent is running on http://localhost:8000")
        return
    
    # Run continuous testing
    await driver.run_continuous_testing(duration_minutes=5)

if __name__ == "__main__":
    asyncio.run(main())