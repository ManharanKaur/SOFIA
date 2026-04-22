import './VoiceAssistantOrb.css';

function VoiceAssistantOrb({ isThinking = false }) {
  const rippleLayers = [0, 1, 2];

  return (
    <div className="voice-orb" aria-label={isThinking ? 'Assistant is thinking' : 'Assistant is idle'}>
      {isThinking && (
        <div className="voice-orb__ripples" aria-hidden="true">
          {rippleLayers.map((layerIndex) => (
            <span
              key={layerIndex}
              className="voice-orb__ripple"
              style={{ animationDelay: `${layerIndex * 0.35}s` }}
            />
          ))}
        </div>
      )}

      <div className="voice-orb__dot" />
    </div>
  );
}

export default VoiceAssistantOrb;