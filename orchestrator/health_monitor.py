import time

class HealthMonitor:
    def __init__(self):
        self.agent_stats = {}

    def register_agent(self, agent_name: str):
        if agent_name not in self.agent_stats:
            self.agent_stats[agent_name] = {
                "status": "idle",
                "last_active": None,
                "successful_tasks": 0,
                "failed_tasks": 0,
                "uptime_start": time.time()
            }

    def set_status(self, agent_name: str, status: str):
        self.register_agent(agent_name)
        self.agent_stats[agent_name]["status"] = status
        # Update last_active whenever the agent starts working (not just "active")
        if status in ("active", "processing"):
            self.agent_stats[agent_name]["last_active"] = time.time()

    def record_success(self, agent_name: str):
        self.register_agent(agent_name)
        self.agent_stats[agent_name]["successful_tasks"] += 1
        self.agent_stats[agent_name]["status"] = "idle"
        # Ensure last_active is set even if set_status was skipped
        if not self.agent_stats[agent_name]["last_active"]:
            self.agent_stats[agent_name]["last_active"] = time.time()

    def record_failure(self, agent_name: str):
        self.register_agent(agent_name)
        self.agent_stats[agent_name]["failed_tasks"] += 1
        self.agent_stats[agent_name]["status"] = "error"
        if not self.agent_stats[agent_name]["last_active"]:
            self.agent_stats[agent_name]["last_active"] = time.time()

    def get_all_stats(self):
        stats_copy = {}
        now = time.time()
        for name, data in self.agent_stats.items():
            stats_copy[name] = data.copy()
            # Human-readable last_active
            if data["last_active"]:
                secs_ago = int(now - data["last_active"])
                if secs_ago < 60:
                    stats_copy[name]["last_active_str"] = "Just now"
                elif secs_ago < 3600:
                    mins_ago = secs_ago // 60
                    stats_copy[name]["last_active_str"] = f"{mins_ago}m ago"
                else:
                    hrs_ago = secs_ago // 3600
                    stats_copy[name]["last_active_str"] = f"{hrs_ago}h ago"
            else:
                stats_copy[name]["last_active_str"] = "Never"

            # Add success rate
            total = data["successful_tasks"] + data["failed_tasks"]
            stats_copy[name]["total_tasks"] = total
            stats_copy[name]["success_rate"] = (
                round(data["successful_tasks"] / total * 100) if total > 0 else None
            )
        return stats_copy

health_monitor = HealthMonitor()
