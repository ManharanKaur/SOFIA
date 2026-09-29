/**
 * PermissionDialog.jsx
 * --------------------
 * Modal dialog shown when SOFIA wants permission to perform a local action.
 *
 * The dialog tells the user:
 *   - Which permission group is being requested (e.g. "Browser Control")
 *   - What that permission allows (description text)
 *   - Offers Allow / Deny buttons and a "Remember this decision" checkbox
 *
 * BEM blocks: permission-dialog, permission-dialog-overlay
 *
 * @param {{
 *   permission: { commandId: string, permission: string, label: string, description: string },
 *   onRespond: (commandId: string, permission: string, granted: boolean, remember: boolean) => void
 * }} props
 */

import { useState } from 'react';
import './PermissionDialog.css';

const PERMISSION_ICONS = {
  browser_control: '🌐',
  app_control:     '📱',
  spotify_control: '🎵',
  system_controls: '🔊',
  file_access:     '📁',
  web_search:      '🔍',
};

function PermissionDialog({ permission, onRespond }) {
  const [rememberDecision, setRememberDecision] = useState(false);

  if (!permission) return null;

  const { commandId, permission: permKey, label, description } = permission;
  const icon = PERMISSION_ICONS[permKey] || '🔐';

  const handleAllow = () => {
    onRespond(commandId, permKey, true, rememberDecision);
  };

  const handleDeny = () => {
    onRespond(commandId, permKey, false, rememberDecision);
  };

  return (
    <>
      <div
        className="permission-dialog-overlay"
        role="presentation"
        onClick={handleDeny}
        aria-hidden="true"
      />

      <dialog
        className="permission-dialog"
        open
        aria-modal="true"
        aria-labelledby="permission-dialog-title"
        aria-describedby="permission-dialog-description"
      >
        <header className="permission-dialog__header">
          <span className="permission-dialog__icon" aria-hidden="true">
            {icon}
          </span>
          <h2
            id="permission-dialog-title"
            className="permission-dialog__title"
          >
            Permission Required
          </h2>
        </header>

        <div className="permission-dialog__body">
          <p className="permission-dialog__prompt">
            <strong>SOFIA</strong> wants{' '}
            <span className="permission-dialog__permission-label">
              {label}
            </span>{' '}
            on your computer.
          </p>

          <p
            id="permission-dialog-description"
            className="permission-dialog__description"
          >
            {description}
          </p>

          <label className="permission-dialog__remember-label">
            <input
              id="permission-dialog-remember"
              className="permission-dialog__remember-checkbox"
              type="checkbox"
              checked={rememberDecision}
              onChange={(event) => setRememberDecision(event.target.checked)}
            />
            <span className="permission-dialog__remember-text">
              Remember this decision
            </span>
          </label>
        </div>

        <footer className="permission-dialog__footer">
          <button
            id="permission-dialog-deny-btn"
            className="permission-dialog__btn permission-dialog__btn--deny"
            type="button"
            onClick={handleDeny}
          >
            Deny
          </button>
          <button
            id="permission-dialog-allow-btn"
            className="permission-dialog__btn permission-dialog__btn--allow"
            type="button"
            onClick={handleAllow}
            autoFocus
          >
            Allow
          </button>
        </footer>
      </dialog>
    </>
  );
}

export default PermissionDialog;
