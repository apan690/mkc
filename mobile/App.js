/**
 * DevMesh Mobile — Triage App (sample end-to-end demo)
 *
 * This is Vatsal's slice of the architecture: the "developer experience
 * layer" that receives findings streamed from the AI PC over local
 * WebSocket, and lets the developer approve / dismiss / expand each one.
 *
 * WHY THIS EXISTS RIGHT NOW:
 * Hardik's real ws_broadcaster.py + LLM pipeline don't exist yet. This app
 * is built against the AGREED SCHEMA below, with a mock server
 * (mock-server/mock_ws_server.py) standing in for the real backend, and a
 * built-in local fallback if no server is reachable at all. That means:
 *   - You can demo the full "commit -> findings on phone" story tonight
 *   - The moment Hardik's real broadcaster exists, you swap SERVER_IP/PORT
 *     and nothing else changes, because the message shape is already fixed
 *
 * WEBSOCKET MESSAGE SCHEMA — matches Hardik's ws_broadcaster.py stub
 * (backend/ws_broadcaster.py, Section 12 skeleton) exactly, as of the
 * payload his broadcast_findings() builds:
 *   {
 *     "file": string,                 // one message per file/hunk
 *     "findings": [
 *       {
 *         "severity": "CRITICAL" | "WARNING" | "SUGGESTION",
 *         "line": number,
 *         "description": string,      // note: "description", not "issue"
 *         "fix": string
 *       }
 *     ]
 *   }
 *
 * NOTE: this is still a STUB on Hardik's side (his function currently just
 * prints this payload, it doesn't send over a real socket yet). The shape
 * is what matters to lock down now, so the mobile app doesn't need to
 * change again once the real WebSocket send is wired up. Re-confirm with
 * Hardik if this shape changes before July 11.
 */

import React, { useEffect, useRef, useState, useCallback } from "react";
import {
  SafeAreaView,
  View,
  Text,
  FlatList,
  StyleSheet,
  TouchableOpacity,
  StatusBar,
  Platform,
} from "react-native";

// ---- CONFIG: point this at your mock server or real backend -------------
// Run `python mock_ws_server.py` on your laptop, then put that machine's
// LAN IP here (phone and laptop must be on the same WiFi).
// Example: "192.168.1.42"
const SERVER_IP = "192.168.0.117";
const SERVER_PORT = 8765;
const WS_URL = `ws://${SERVER_IP}:${SERVER_PORT}`;

// If no server is reachable within this window, fall back to local mock
// data so the UI is still fully demoable standalone (e.g. showing the app
// to a teammate with no laptop nearby).
const CONNECTION_TIMEOUT_MS = 3000;

// Flat, UI-friendly shape used internally once messages are unpacked.
// (Raw wire messages are grouped by file — see flattenPayload below.)
const FALLBACK_FINDINGS = [
  {
    severity: "CRITICAL",
    file: "auth.py",
    line: 42,
    description: "SQL injection vulnerability",
    fix: "Use parameterized queries instead of string formatting",
  },
  {
    severity: "WARNING",
    file: "utils.py",
    line: 17,
    description: "Unused import 'os'",
    fix: "Remove the unused import",
  },
  {
    severity: "SUGGESTION",
    file: "helpers.py",
    line: 55,
    description: "Consider extracting to separate function",
    fix: "Pull the repeated block into a named helper",
  },
];

// Unpacks Hardik's wire format { file, findings: [...] } into a flat array
// of { severity, file, line, description, fix } objects the UI can render
// one card per finding for, regardless of how many findings share a file.
function flattenPayload(payload) {
  if (!payload || !Array.isArray(payload.findings)) return [];
  return payload.findings.map((f) => ({
    severity: f.severity,
    file: payload.file,
    line: f.line,
    description: f.description,
    fix: f.fix,
  }));
}

const SEVERITY_STYLES = {
  CRITICAL: { color: "#EF4444", bg: "#FEF2F2", icon: "\u{1F534}", label: "CRITICAL" },
  WARNING: { color: "#D97706", bg: "#FFFBEB", icon: "\u{1F7E1}", label: "WARNING" },
  SUGGESTION: { color: "#16A34A", bg: "#F0FDF4", icon: "\u{1F7E2}", label: "SUGGESTION" },
};

function makeId(finding, index) {
  return `${finding.file}:${finding.line}:${index}`;
}

export default function App() {
  const [findings, setFindings] = useState([]);
  const [status, setStatus] = useState("connecting"); // connecting | live | waiting
  const [expandedIds, setExpandedIds] = useState({});
  const [decisions, setDecisions] = useState({}); // id -> "approved" | "dismissed"
  const [attemptCount, setAttemptCount] = useState(0);
  const [demoActive, setDemoActive] = useState(false);

  const wsRef = useRef(null);
  const reconnectTimerRef = useRef(null);

  const showDemoData = useCallback(() => {
    setDemoActive(true);
    setFindings(FALLBACK_FINDINGS);
  }, []);

  const hideDemoData = useCallback(() => {
    setDemoActive(false);
    setFindings([]);
  }, []);

useEffect(() => {
  let mounted = true;
  let reconnectAttempts = 0;
  const MAX_RETRIES = 20;

  const connect = () => {
    if (!mounted) return;

    reconnectAttempts += 1;
    if (mounted) setAttemptCount(reconnectAttempts);

    console.log(
      `[DevMesh] Connecting attempt ${reconnectAttempts}`
    );
    console.log("[DevMesh] URL:", WS_URL);

    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    const timeout = setTimeout(() => {
      if (
        ws.readyState !== WebSocket.OPEN &&
        mounted
      ) {
        console.log(
          "[DevMesh] Connection timeout"
        );
        setStatus("waiting");
        ws.close();
      }
    }, CONNECTION_TIMEOUT_MS);

    ws.onopen = () => {
      clearTimeout(timeout);

      console.log("[DevMesh] CONNECTED");

      reconnectAttempts = 0;

      if (mounted) {
        setStatus("live");
        setAttemptCount(0);
        // Real data has arrived — drop any demo/sample data so it can
        // never be mistaken for a live finding.
        setDemoActive(false);
        setFindings([]);
      }
    };

    ws.onmessage = (event) => {
      console.log(
        "[DevMesh] RAW:",
        event.data
      );

      try {
        const payload = JSON.parse(
          event.data
        );

        const newFindings =
          flattenPayload(payload);

        if (
          mounted &&
          newFindings.length > 0
        ) {
          setFindings((prev) => [
            ...prev,
            ...newFindings,
          ]);
        }
      } catch (e) {
        console.warn(
          "[DevMesh] Parse error:",
          e
        );
      }
    };

    ws.onerror = (e) => {
      console.log(
        "[DevMesh] ERROR:",
        e.message || e
      );
    };

    ws.onclose = () => {
      clearTimeout(timeout);

      console.log(
        "[DevMesh] SOCKET CLOSED"
      );

      if (!mounted) return;

      if (mounted) setStatus("waiting");

      if (
        reconnectAttempts < MAX_RETRIES
      ) {
        const delay = Math.min(
          reconnectAttempts * 1000,
          5000
        );

        console.log(
          `[DevMesh] Reconnecting in ${delay}ms`
        );

        reconnectTimerRef.current =
          setTimeout(() => {
            connect();
          }, delay);
      }
    };
  };

  connect();

  return () => {
    mounted = false;

    clearTimeout(
      reconnectTimerRef.current
    );

    if (wsRef.current) {
      wsRef.current.onclose = null;
      wsRef.current.close();
    }
  };
}, []);

  const toggleExpand = (id) => {
    setExpandedIds((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const decide = (id, decision) => {
    setDecisions((prev) => ({ ...prev, [id]: decision }));
  };

  const renderItem = ({ item, index }) => {
    const id = makeId(item, index);
    const sev = SEVERITY_STYLES[item.severity] || SEVERITY_STYLES.SUGGESTION;
    const expanded = !!expandedIds[id];
    const decision = decisions[id];

    return (
      <View style={[styles.card, { backgroundColor: sev.bg, borderLeftColor: sev.color }]}>
        <View style={styles.cardHeader}>
          <Text style={[styles.severityBadge, { color: sev.color }]}>
            {sev.icon} {sev.label}
          </Text>
          <Text style={styles.location}>
            {item.file}:{item.line}
          </Text>
        </View>

        <Text style={styles.issue}>{item.description}</Text>

        {expanded && (
          <View style={styles.fixBox}>
            <Text style={styles.fixLabel}>Recommended fix</Text>
            <Text style={styles.fixText}>{item.fix}</Text>
          </View>
        )}

        <View style={styles.actionRow}>
          <TouchableOpacity onPress={() => toggleExpand(id)} style={styles.actionButtonGhost}>
            <Text style={styles.actionGhostText}>{expanded ? "Hide fix" : "Explain"}</Text>
          </TouchableOpacity>

          <TouchableOpacity
            onPress={() => decide(id, "dismissed")}
            style={[
              styles.actionButtonGhost,
              decision === "dismissed" && styles.actionDismissedActive,
            ]}
          >
            <Text style={styles.actionGhostText}>
              {decision === "dismissed" ? "Dismissed" : "Dismiss"}
            </Text>
          </TouchableOpacity>

          <TouchableOpacity
            onPress={() => decide(id, "approved")}
            style={[styles.actionButtonSolid, decision === "approved" && styles.actionApprovedActive]}
          >
            <Text style={styles.actionSolidText}>
              {decision === "approved" ? "\u2713 Approved" : "Approve"}
            </Text>
          </TouchableOpacity>
        </View>
      </View>
    );
  };

  const statusLabel = {
    connecting: "Connecting to review server...",
    live: "Live \u2014 streaming from AI PC",
    waiting: `Waiting for AI PC${attemptCount > 1 ? ` (attempt ${attemptCount})` : ""}`,
  }[status];

  const statusColor = status === "live" ? "#16A34A" : status === "waiting" ? "#64748B" : "#94A3B8";
  const showDemoBanner = demoActive && status !== "live";

  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar barStyle="light-content" backgroundColor="#0F172A" />
      <View style={styles.header}>
        <Text style={styles.headerTitle}>DevMesh</Text>
        <Text style={styles.headerSubtitle}>On-device code review, in your pocket</Text>
        <View style={styles.statusRow}>
          <View style={[styles.statusDot, { backgroundColor: statusColor }]} />
          <Text style={styles.statusText}>{statusLabel}</Text>
        </View>
        {showDemoBanner && (
          <View style={styles.demoBanner}>
            <Text style={styles.demoBannerText}>SAMPLE DATA — not from a live review</Text>
            <TouchableOpacity onPress={hideDemoData}>
              <Text style={styles.demoBannerAction}>Hide</Text>
            </TouchableOpacity>
          </View>
        )}
      </View>

      <FlatList
        data={findings}
        keyExtractor={(item, index) => makeId(item, index)}
        renderItem={renderItem}
        contentContainerStyle={styles.listContent}
        ListEmptyComponent={
          <View style={styles.emptyState}>
            <Text style={styles.emptyText}>
              {status === "live"
                ? "Waiting for findings..."
                : "Not connected to the AI PC yet."}
            </Text>
            {status !== "live" && (
              <TouchableOpacity onPress={showDemoData} style={styles.demoButton}>
                <Text style={styles.demoButtonText}>Show Demo Data</Text>
              </TouchableOpacity>
            )}
          </View>
        }
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: "#0F172A",
  },
  header: {
    paddingHorizontal: 20,
    paddingTop: Platform.OS === "android" ? 20 : 8,
    paddingBottom: 16,
    backgroundColor: "#0F172A",
  },
  headerTitle: {
    color: "#FFFFFF",
    fontSize: 26,
    fontWeight: "700",
  },
  headerSubtitle: {
    color: "#94A3B8",
    fontSize: 13,
    marginTop: 2,
  },
  statusRow: {
    flexDirection: "row",
    alignItems: "center",
    marginTop: 10,
  },
  statusDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    marginRight: 8,
  },
  statusText: {
    color: "#CBD5E1",
    fontSize: 12,
  },
  listContent: {
    padding: 16,
    paddingBottom: 40,
    backgroundColor: "#F1F5F9",
    flexGrow: 1,
  },
  emptyState: {
    marginTop: 60,
    alignItems: "center",
  },
  emptyText: {
    color: "#94A3B8",
    fontSize: 14,
    marginBottom: 16,
  },
  demoButton: {
    borderWidth: 1,
    borderColor: "#CBD5E1",
    borderRadius: 8,
    paddingVertical: 8,
    paddingHorizontal: 16,
  },
  demoButtonText: {
    color: "#475569",
    fontSize: 13,
    fontWeight: "600",
  },
  demoBanner: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    backgroundColor: "#78350F",
    borderRadius: 8,
    paddingVertical: 6,
    paddingHorizontal: 10,
    marginTop: 10,
  },
  demoBannerText: {
    color: "#FDE68A",
    fontSize: 11,
    fontWeight: "700",
    letterSpacing: 0.3,
  },
  demoBannerAction: {
    color: "#FDE68A",
    fontSize: 11,
    fontWeight: "700",
    textDecorationLine: "underline",
  },
  card: {
    borderRadius: 12,
    borderLeftWidth: 4,
    padding: 14,
    marginBottom: 12,
  },
  cardHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 6,
  },
  severityBadge: {
    fontWeight: "700",
    fontSize: 12,
    letterSpacing: 0.5,
  },
  location: {
    fontSize: 12,
    color: "#475569",
    fontFamily: Platform.OS === "ios" ? "Menlo" : "monospace",
  },
  issue: {
    fontSize: 15,
    color: "#0F172A",
    fontWeight: "500",
    marginBottom: 8,
  },
  fixBox: {
    backgroundColor: "rgba(255,255,255,0.6)",
    borderRadius: 8,
    padding: 10,
    marginBottom: 10,
  },
  fixLabel: {
    fontSize: 11,
    fontWeight: "700",
    color: "#334155",
    marginBottom: 3,
    textTransform: "uppercase",
  },
  fixText: {
    fontSize: 13,
    color: "#1E293B",
  },
  actionRow: {
    flexDirection: "row",
    justifyContent: "flex-end",
    gap: 8,
  },
  actionButtonGhost: {
    paddingVertical: 6,
    paddingHorizontal: 10,
    borderRadius: 8,
  },
  actionGhostText: {
    fontSize: 12,
    color: "#475569",
    fontWeight: "600",
  },
  actionDismissedActive: {
    backgroundColor: "rgba(100,116,139,0.15)",
  },
  actionButtonSolid: {
    paddingVertical: 6,
    paddingHorizontal: 12,
    borderRadius: 8,
    backgroundColor: "#0F172A",
  },
  actionSolidText: {
    fontSize: 12,
    color: "#FFFFFF",
    fontWeight: "700",
  },
  actionApprovedActive: {
    backgroundColor: "#16A34A",
  },
});