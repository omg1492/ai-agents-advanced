import { useCallback, useEffect, useMemo, useSyncExternalStore } from 'react';
import { Mic, MicOff, Volume2, VolumeX } from 'lucide-react';
import { voiceSessionManager } from '@/lib/voice-session-manager';
import { Button } from './ui/button';
import { Tooltip, TooltipContent, TooltipTrigger } from './ui/tooltip';

interface VoiceButtonProps {
  threadId: string | null;
  onTranscript?: (role: 'user' | 'assistant', text: string) => void;
}

/**
 * Voice conversation button that delegates session lifecycle management to the
 * voiceSessionManager singleton. The manager owns all Audio/WebSocket state so
 * a React remount no longer interrupts the first start attempt.
 */
export function VoiceButton({ threadId, onTranscript }: VoiceButtonProps) {
  const session = useSyncExternalStore(
    voiceSessionManager.subscribe,
    voiceSessionManager.getSnapshot,
    voiceSessionManager.getSnapshot,
  );

  useEffect(() => {
    console.log('[VoiceButton] 🔄 Installing transcript handler on manager');
    voiceSessionManager.setTranscriptHandler(onTranscript);
  }, [onTranscript]);

  const isVoiceActive = session.wsReadyState === WebSocket.OPEN;
  const effectiveStatus = isVoiceActive ? 'active' : session.status;

  useEffect(() => {
    console.log('[VoiceButton] 🔍 Session snapshot changed', {
      status: session.status,
      effectiveStatus,
      wsReadyState: session.wsReadyState,
      isMuted: session.isMuted,
      error: session.error,
      lastUpdated: session.lastUpdated,
    });
  }, [effectiveStatus, session.error, session.isMuted, session.lastUpdated, session.status, session.wsReadyState]);

  const handleToggle = useCallback(() => {
    const ws = voiceSessionManager.getWebSocket();
    const wsStateString = ws ? ['CONNECTING', 'OPEN', 'CLOSING', 'CLOSED'][ws.readyState] : 'NONE';
    console.log('[VoiceButton] 🔘 Toggle pressed', {
      currentStatus: session.status,
      effectiveStatus,
      wsStateString,
      threadId,
    });

    if (ws && ws.readyState === WebSocket.OPEN) {
      voiceSessionManager.stop('user-toggle');
      return;
    }

    if (session.status === 'connecting') {
      console.warn('[VoiceButton] ⚠️ Already connecting; ignoring duplicate click');
      return;
    }

    void voiceSessionManager.start({ threadId, onTranscript });
  }, [effectiveStatus, onTranscript, session.status, threadId]);

  const handleMute = useCallback(() => {
    voiceSessionManager.toggleMute();
  }, []);

  const buttonClasses = useMemo(() => {
    if (effectiveStatus === 'error') return 'bg-red-600 hover:bg-red-700';
    if (isVoiceActive) return 'bg-green-600 hover:bg-green-700';
    return 'bg-blue-600 hover:bg-blue-700';
  }, [effectiveStatus, isVoiceActive]);

  const buttonText = useMemo(() => {
    if (isVoiceActive) return 'Stop Voice';
    if (effectiveStatus === 'error') return 'Error - Try Again';
    if (effectiveStatus === 'connecting') return 'Connecting...';
    return 'Start Voice';
  }, [effectiveStatus, isVoiceActive]);

  return (
    <div className="flex gap-2">
      <Tooltip>
        <TooltipTrigger asChild>
          <Button
            onClick={handleToggle}
            disabled={session.status === 'connecting'}
            className={`${buttonClasses} text-white`}
            size="sm"
          >
            {isVoiceActive ? <Mic className="h-4 w-4" /> : <MicOff className="h-4 w-4" />}
            <span className="ml-2">{buttonText}</span>
          </Button>
        </TooltipTrigger>
        <TooltipContent>
          {isVoiceActive ? 'Stop voice conversation' : 'Start voice conversation (speech-to-speech)'}
        </TooltipContent>
      </Tooltip>

      {isVoiceActive && (
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              onClick={handleMute}
              variant="outline"
              size="sm"
            >
              {session.isMuted ? <VolumeX className="h-4 w-4" /> : <Volume2 className="h-4 w-4" />}
            </Button>
          </TooltipTrigger>
          <TooltipContent>
            {session.isMuted ? 'Unmute microphone' : 'Mute microphone'}
          </TooltipContent>
        </Tooltip>
      )}
    </div>
  );
}
