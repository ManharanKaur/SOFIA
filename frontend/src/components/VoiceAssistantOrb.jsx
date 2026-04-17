import './VoiceAssistantOrb.css';

/**
 * VoiceAssistantOrb
 *
 * A simple visual for a voice assistant.
 * - When isThinking is false: only the center blue dot is shown.
 * - When isThinking is true: 3 ripple waves animate around the dot.
 */
function VoiceAssistantOrb({ isThinking = false }) {
  // We create 3 ripple layers so the waves look continuous and smooth.
  const rippleLayers = [0, 1, 2];

  return (
    // Outer wrapper keeps the orb centered in its own area.
    <div className="voice-orb" aria-label={isThinking ? 'Assistant is thinking' : 'Assistant is idle'}>
      {/* Ripple waves are only rendered while the assistant is thinking. */}
      {isThinking && (
        <div className="voice-orb__ripples" aria-hidden="true">
          {rippleLayers.map((layerIndex) => (
            <span
              key={layerIndex}
              className="voice-orb__ripple"
              // Stagger each ripple with a slight delay for a wave effect.
              style={{ animationDelay: `${layerIndex * 0.35}s` }}
            />
          ))}
        </div>
      )}

      {/* This is the static center blue dot. It is always visible. */}
      <div className="voice-orb__dot" />
    </div>
  );
}

export default VoiceAssistantOrb;