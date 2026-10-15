"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getProfile, User } from "@/lib/api";

export default function Home() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) {
      router.push("/login");
      return;
    }

    getProfile(token)
      .then((data) => {
        setUser(data);
        setLoading(false);
      })
      .catch(() => {
        // Invalid or expired token
        localStorage.removeItem("token");
        localStorage.removeItem("user");
        router.push("/login");
      });
  }, [router]);

  const handleLogout = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    router.push("/login");
  };

  if (loading) {
    return (
      <main className="dashboard-page">
        <div className="dashboard-card">
          <div className="spinner" style={{ width: "36px", height: "36px" }} />
          <p style={{ marginTop: "1rem", color: "var(--text-secondary)" }}>
            Verifying authentication...
          </p>
        </div>
      </main>
    );
  }

  const initial = user?.name ? user.name.charAt(0).toUpperCase() : "U";

  return (
    <main className="dashboard-page">
      <div className="dashboard-card">
        <div className="dashboard-avatar">{initial}</div>
        <span className="badge-success">
          <span style={{ width: "6px", height: "6px", borderRadius: "50%", background: "#10b981" }} />
          Authenticated Session
        </span>
        <h1 className="dashboard-name">Welcome, {user?.name}!</h1>
        <p className="dashboard-email">{user?.email}</p>

        <div style={{ textAlign: "left", background: "rgba(0,0,0,0.2)", padding: "1rem", borderRadius: "12px", marginBottom: "1.5rem", fontSize: "0.85rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.5rem" }}>
            <span style={{ color: "var(--text-muted)" }}>User ID:</span>
            <span style={{ fontFamily: "monospace", color: "var(--accent-light)" }}>{user?.id}</span>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between" }}>
            <span style={{ color: "var(--text-muted)" }}>Account Created:</span>
            <span style={{ color: "var(--text-secondary)" }}>
              {user?.created_at ? new Date(user.created_at).toLocaleDateString() : "N/A"}
            </span>
          </div>
        </div>

        <button onClick={handleLogout} className="btn-primary" style={{ background: "linear-gradient(135deg, #ef4444, #dc2626)" }}>
          Sign Out
        </button>
      </div>
    </main>
  );
}
