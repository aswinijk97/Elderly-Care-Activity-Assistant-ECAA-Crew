import time
import json
from datetime import datetime, timedelta

# --- 1. CORE SIMULATION COMPONENTS (LLM, TOOLS, STATE) ---

class LLMSimulator:
    """
    Mocks the behavior of the Gemini LLM for reasoning and response generation.
    In a real system, this would be an API call to Gemini-2.5-Flash.
    """
    @staticmethod
    def health_manager_reasoning(task: str, user_response: str) -> dict:
        """
        Simulates the Health Manager Agent's reasoning, which uses the LLM
        to determine compliance status and next action (A2A artifact).
        This output models a Pydantic/JSON schema for safety.
        """
        print(f"\n[LLM-H: Reasoning on Compliance for: {task}]")
        if "confirm" in user_response.lower() or "took" in user_response.lower():
            # SUCCESS PATH
            status = "confirmed"
            next_action = "none"
            response_text = "Compliance confirmed. Well done!"
        elif user_response == "TIMEOUT":
            # ESCALATION PATH
            status = "missed"
            next_action = "alert_caregiver"
            response_text = "Dose missed. Initiating caregiver alert."
        else:
            # INTERACTION PATH (User is confused/asks a question)
            status = "pending_follow_up"
            next_action = "none"
            response_text = f"I see you asked about: '{user_response}'. Let me check the database for you."

        return {
            "a2a_status": status,
            "next_action": next_action,
            "response_text": response_text
        }

    @staticmethod
    def activity_coordinator_response(query: str) -> str:
        """
        Simulates the Activity Coordinator's general conversational LLM response.
        """
        print(f"\n[LLM-A: Generating conversational response for: {query}]")
        if "breakfast" in query.lower():
            return "That's a great question! Based on your low-sodium diet and favorite foods log, I recommend a small bowl of oatmeal with berries and a glass of milk."
        return "I can help with that. Let me look up some options for you."

class CustomTools:
    """
    Mocks external services and APIs that agents call (Function Tools).
    """
    @staticmethod
    def send_alert_to_caregiver(message: str):
        """Mocks sending a critical SMS/Email alert to the caregiver."""
        print(f"🚨 TOOL CALL: Caregiver Alert Sent!")
        print(f"   [Notification Service]: **URGENT:** {message}")
        print("   --- Escalation complete. Resuming Planner Loop. ---")
        return True

    @staticmethod
    def retrieve_long_term_memory(query: str) -> str:
        """
        Mocks a RAG call to a Vector Database containing health records.
        """
        if "Blood Pressure" in query:
            return "Retrieved: Blood Pressure Med (Lisinopril 10mg) is taken daily at 8:00 AM. Key interaction: Avoid grapefruit juice."
        return "Retrieved: No critical information found for that query."

# --- 2. SESSION STATE (SHARED MEMORY) ---

class SessionState:
    """
    Simulates the shared state across all agents (like a Redis or Firestore document).
    This is the persistent, high-context memory.
    """
    def __init__(self):
        self.current_time = datetime.now().replace(second=0, microsecond=0)
        self.user_profile = {"name": "Mr. David", "health_data": "Low-sodium diet, Allergic to Penicillin"}
        self.daily_schedule = {
            "8:00": {"task": "Medication: Blood Pressure Med", "status": "PENDING", "priority": "CRITICAL"},
            "10:30": {"task": "Activity: Walk 15 minutes", "status": "PENDING", "priority": "LOW"},
            "15:00": {"task": "Medication: Vitamin D", "status": "PENDING", "priority": "HIGH"},
        }
        self.escalation_log = []

# --- 3. AGENT DEFINITIONS ---

class HealthManagerAgent:
    """Specialized agent for high-priority health and compliance tasks."""
    def __init__(self, llm_simulator: LLMSimulator, session_state: SessionState):
        self.llm = llm_simulator
        self.state = session_state

    def issue_reminder_and_check_compliance(self, task_time: str, task_details: dict) -> dict:
        """
        Executes the critical sequence: reminder -> wait for compliance -> A2A decision.
        Returns a structured A2A artifact.
        """
        med_info = CustomTools.retrieve_long_term_memory(task_details['task'])
        print(f"\n>>> HEALTH MANAGER (💊) triggered at {task_time} <<<")
        print(f"   Reminder Issued to User: Good morning, {self.state.user_profile['name']}! Time for your {task_details['task']}. {med_info}")

        # --- SIMULATE USER INTERACTION / TIMEOUT ---
        # In a real app, this would be a UI/voice prompt awaiting a response.
        if task_time == "8:00":
            # Simulate a timeout (Missed Dose Scenario)
            print("\n   ... Simulating 15-minute timeout with no user confirmation ...")
            user_response = "TIMEOUT"
        else:
            # Simulate a successful confirmation
            user_response = "I confirm I took it. Thanks."

        # Use the LLM to process the result and generate the A2A artifact
        llm_output = self.llm.health_manager_reasoning(task_details['task'], user_response)

        # Update the internal state for the current day
        if llm_output['a2a_status'] == 'missed':
            self.state.daily_schedule[task_time]['status'] = 'MISSED - ESCALATED'
            self.state.escalation_log.append(f"{self.state.current_time.strftime('%H:%M')} - {task_details['task']} missed.")

        print(f"   {task_details['task']} Status: {llm_output['a2a_status'].upper()}")

        # RETURN A2A ARTIFACT (Structured Data Transfer)
        return {
            "agent_source": "HealthManagerAgent",
            "task": task_details['task'],
            "a2a_artifact": llm_output
        }

class ActivityCoordinatorAgent:
    """Specialized agent for general information and activity planning."""
    def __init__(self, llm_simulator: LLMSimulator, session_state: SessionState):
        self.llm = llm_simulator
        self.state = session_state

    def handle_user_query(self, query: str):
        """Responds to general user requests using conversational LLM."""
        print("\n>>> ACTIVITY COORDINATOR (🏡) activated <<<")
        response = self.llm.activity_coordinator_response(query)
        print(f"   Coordinator Response: {response}")
        return response

class PlannerAgent:
    """The Orchestrator and Loop Agent. Manages time, state, and delegation."""
    def __init__(self, session_state: SessionState, health_manager: HealthManagerAgent, activity_coordinator: ActivityCoordinatorAgent):
        self.state = session_state
        self.health_manager = health_manager
        self.activity_coordinator = activity_coordinator

    def process_a2a_artifact(self, artifact: dict):
        """
        Crucial step: The Planner Agent reads the structured A2A output
        and executes deterministic logic based on the status.
        """
        a2a_data = artifact.get('a2a_artifact', {})
        status = a2a_data.get('a2a_status')
        next_action = a2a_data.get('next_action')

        print(f"\n[PLANNER (🧠): Processing A2A Artifact from {artifact['agent_source']}]")
        print(f"   Status: {status.upper()} | Next Action: {next_action.upper()}")

        if status == "missed" and next_action == "alert_caregiver":
            # Execute the critical, high-stakes tool
            print("   --- CRITICAL ESCALATION LOGIC ACTIVATED ---")
            CustomTools.send_alert_to_caregiver(
                f"{self.state.user_profile['name']} missed their {artifact['task']}."
            )
        elif status == "confirmed":
            print(f"   Compliance for {artifact['task']} logged. State updated.")
        else:
            print("   A2A handled. No further immediate action required.")

    def run_step(self):
        """
        Simulates one step of the Loop: checks the time and triggers
        the appropriate agent or logic.
        """
        current_time_str = self.state.current_time.strftime("%H:%M")
        print(f"\n--- PLANNER LOOP STEP: {current_time_str} ---")

        # 1. CHECK SCHEDULE (The Loop Functionality)
        if current_time_str in self.state.daily_schedule:
            task_details = self.state.daily_schedule[current_time_str]
            if task_details['status'] == 'PENDING':
                print(f"   Scheduled Task Found: {task_details['task']}")

                # 2. DELEGATION (Sequential Workflow)
                if task_details['priority'] in ['CRITICAL', 'HIGH']:
                    print("   Delegating to Health Manager (High Priority).")
                    a2a_artifact = self.health_manager.issue_reminder_and_check_compliance(current_time_str, task_details)

                    # 3. A2A PROTOCOL & ESCALATION
                    self.process_a2a_artifact(a2a_artifact)

                    # Update internal state status to prevent repeated action
                    self.state.daily_schedule[current_time_str]['status'] = 'COMPLETED'
                else:
                    print("   Delegating to Activity Coordinator (Low Priority).")
                    # For low-priority tasks, simply mark as completed for the simulation
                    self.state.daily_schedule[current_time_str]['status'] = 'COMPLETED'
                    print(f"   {task_details['task']} marked as done.")

        else:
            print("   No scheduled task at this time. Monitoring ambient environment.")


# --- 4. EXECUTION SIMULATION ---

def run_eca_crew_simulation():
    """
    Main function to initialize and run the simulation, demonstrating the
    high-priority escalation scenario.
    """
    print("=======================================================================")
    print("       ELDERLY CARE & ACTIVITY ASSISTANT (ECAA) CREW SIMULATION        ")
    print("=======================================================================")

    # Setup the Environment and Agents
    state = SessionState()
    llm = LLMSimulator()
    health_manager = HealthManagerAgent(llm, state)
    activity_coordinator = ActivityCoordinatorAgent(llm, state)
    planner = PlannerAgent(state, health_manager, activity_coordinator)

    # Set initial time for the simulation to trigger the CRITICAL event
    state.current_time = state.current_time.replace(hour=8, minute=0, second=0)

    print(f"Simulation Start Time: {state.current_time.strftime('%Y-%m-%d %H:%M')}")
    print(f"Target User: {state.user_profile['name']}\n")

    # --- SIMULATION STEP 1: CRITICAL REMINDER & TIMEOUT ---
    print("\n\n--- SIMULATING TIME: 8:00 AM (CRITICAL MEDICATION TIME) ---")
    planner.run_step()

    # The Planner receives the A2A artifact which flags "missed" and triggers the alert tool.
    print("\n[Simulation Point: Critical Escalation Executed and Logged]")
    print(f"Escalation Log: {state.escalation_log}")

    # --- SIMULATION STEP 2: USER CONVERSATION DURING ESCALATION ---
    state.current_time += timedelta(minutes=1) # Advance time slightly
    user_query = "What should I eat for breakfast?"
    print(f"\n\n--- SIMULATING USER INTERACTION AT 8:01 AM ---")
    print(f"User Query: '{user_query}'")

    # The Activity Coordinator can run in parallel while the background action (alert) finishes.
    coordinator_response = activity_coordinator.handle_user_query(user_query)


    # --- SIMULATION STEP 3: LATER, SUCCESSFUL TASK ---
    state.current_time = state.current_time.replace(hour=15, minute=0, second=0)
    print("\n\n--- SIMULATING TIME: 3:00 PM (SUCCESSFUL MEDICATION TASK) ---")
    planner.run_step()

    print("\n=======================================================================")
    print("                     SIMULATION END OF DAY SUMMARY                     ")
    print("=======================================================================")
    print("Final Daily Schedule Status:")
    print(json.dumps(state.daily_schedule, indent=4))
    print("\nFinal Escalation Log:")
    print(state.escalation_log)


if __name__ == "__main__":
    run_eca_crew_simulation()
