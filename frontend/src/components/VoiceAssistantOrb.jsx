/**
 * VoiceAssistantOrb.jsx
 * ---------------------
 * Animated orb that visualises SOFIA's current state.
 *
 * Ripple delay is expressed via a CSS custom property (--ripple-delay)
 * instead of an inline style, keeping the component free of inline CSS.
 *
 * BEM block: voice-orb
 */

import './VoiceAssistantOrb.css';

const RIPPLE_LAYERS = [0, 1, 2];

/**
 * @param {{ isThinking: boolean }} props
 */
function VoiceAssistantOrb({ isThinking = false }) {
  return (
    <div
      className={`voice-orb${isThinking ? ' voice-orb--thinking' : ''}`}
      aria-label={isThinking ? 'Assistant is thinking' : 'Assistant is idle'}
    >
      <div className="voice-orb__ripples" aria-hidden="true">
        {RIPPLE_LAYERS.map((layerIndex) => (
          <span
            key={layerIndex}
            className="voice-orb__ripple"
            data-delay={layerIndex}
          />
        ))}
      </div>

      <div className="voice-orb__dot" />
    </div>
  );
}

export default VoiceAssistantOrb;