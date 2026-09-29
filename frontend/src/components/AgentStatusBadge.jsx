/**
 * AgentStatusBadge.jsx
 * --------------------
 * Displays the connection state of the SOFIA Desktop Agent.
 *
 * States
 * ------
 * connected     — agent is connected; computer-control commands work
 * disconnected  — agent is not running; computer-control commands unavailable
 * waiting       — a permission request is pending user approval
 *
 * BEM blocks: agent-status-badge
 */

import './AgentStatusBadge.css';

/**
 * @param {{ agentConnected: boolean, hasPendingPermission: boolean }} props
 */
function AgentStatusBadge({ agentConnected, hasPendingPermission }) {
  let modifier = 'disconnected';
  let labelText = 'Agent Offline';

  if (hasPendingPermission) {
    modifier = 'waiting';
    labelText = 'Waiting for Permission';
  } else if (agentConnected) {
    modifier = 'connected';
    labelText = 'Agent Connected';
  }

  return (
    <div
      className={`agent-status-badge agent-status-badge--${modifier}`}
      title={
        agentConnected
          ? 'SOFIA Desktop Agent is running. Computer-control commands are available.'
          : 'SOFIA Desktop Agent is not running. Install and start it to control your computer.'
      }
      aria-label={`Desktop Agent status: ${labelText}`}
    >
      <span className="agent-status-badge__indicator" aria-hidden="true" />
      <span className="agent-status-badge__label">{labelText}</span>
    </div>
  );
}

export default AgentStatusBadge;
