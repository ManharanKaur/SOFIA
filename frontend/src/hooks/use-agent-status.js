/**
 * use-agent-status.js
 * --------------------
 * Custom React hook that polls the Render backend's /api/agent/status
 * endpoint every 5 seconds to determine whether the SOFIA Desktop Agent
 * is currently connected.
 *
 * Also polls for pending permission requests that need user approval.
 *
 * Returns
 * -------
 * {
 *   agentConnected: boolean,
 *   pendingPermission: object | null,   // { commandId, permission, label, description }
 *   respondToPermission: (commandId, permission, granted, remember) => void
 * }
 */

import { useState, useEffect, useCallback, useRef } from 'react';

const POLL_INTERVAL_MS = 5000;

/**
 * @param {string|null} backendBase  The resolved Render backend base URL.
 */
function useAgentStatus(backendBase) {
  const [agentConnected, setAgentConnected] = useState(false);
  const [pendingPermission, setPendingPermission] = useState(null);
  const pollTimerRef = useRef(null);

  // ── Poll agent connection status ─────────────────────────────────────────

  const pollStatus = useCallback(async () => {
    if (!backendBase) return;

    try {
      const response = await fetch(`${backendBase}/api/agent/status`);
      if (!response.ok) return;

      const data = await response.json();
      setAgentConnected(Boolean(data.connected));
    } catch {
      // Silently ignore network errors; the backend health check handles those.
    }
  }, [backendBase]);

  useEffect(() => {
    if (!backendBase) return undefined;

    pollStatus();
    pollTimerRef.current = setInterval(pollStatus, POLL_INTERVAL_MS);

    return () => {
      if (pollTimerRef.current) {
        clearInterval(pollTimerRef.current);
      }
    };
  }, [backendBase, pollStatus]);

  // ── Handle permission response from the user ─────────────────────────────

  const respondToPermission = useCallback(
    async (commandId, permission, granted, remember) => {
      if (!backendBase) return;

      try {
        await fetch(`${backendBase}/api/permission/respond`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            command_id: commandId,
            permission,
            granted,
            remember,
          }),
        });
      } catch (error) {
        console.error('Failed to send permission response:', error);
      } finally {
        setPendingPermission(null);
      }
    },
    [backendBase],
  );

  // ── Expose a setter so App.jsx can surface permission requests ───────────

  const showPermissionRequest = useCallback((permissionData) => {
    setPendingPermission(permissionData);
  }, []);

  return {
    agentConnected,
    pendingPermission,
    setPendingPermission: showPermissionRequest,
    respondToPermission,
  };
}

export default useAgentStatus;
