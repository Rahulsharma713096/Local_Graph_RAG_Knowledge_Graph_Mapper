import { useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Cpu, Loader2, Radio, Zap, CheckCircle2, AlertCircle, Clock, Sparkles } from 'lucide-react';
import type { BufferingEvent, BufferingState } from '../../types';

interface Props {
  buffering: BufferingState | null;
  className?: string;
  compact?: boolean;
}

export function BufferingIndicator({ buffering, className = '', compact = false }: Props) {
  const [showDetails, setShowDetails] = useState(false);
  const prevCharsRef = useRef(0);

  if (!buffering || !buffering.active) return null;

  const elapsed = buffering.elapsedSeconds;
  const charsPerSecond = elapsed > 0 ? Math.round(buffering.charsBuffered / elapsed) : 0;
  const isWaitingForModel = buffering.charsBuffered === 0 && elapsed < 3;
  const isActivelyBuffering = buffering.charsBuffered > 0;
  const isSlow = elapsed > 10 && charsPerSecond < 5;

  if (compact) {
    return (
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -10 }}
        className={`flex items-center gap-2 px-3 py-1.5 rounded-lg bg-primary-500/10 border border-primary-500/20 ${className}`}
      >
        <div className="relative">
          <Loader2 className="w-3.5 h-3.5 text-primary-400 animate-spin" />
          <span className="absolute inset-0 w-3.5 h-3.5 animate-ping rounded-full bg-primary-400/20" />
        </div>
        <span className="text-xs text-primary-400 font-medium">Buffering...</span>
        {elapsed > 0 && (
          <span className="text-[10px] text-gray-500 font-mono">{elapsed.toFixed(1)}s</span>
        )}
      </motion.div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.95 }}
      className={`glass-card border-primary-500/30 overflow-hidden ${className}`}
    >
      {/* Header */}
      <div className="px-4 py-3 bg-primary-500/5 border-b border-primary-500/10 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="relative">
            <Loader2 className="w-4 h-4 text-primary-400 animate-spin" />
            <span className="absolute inset-0 w-4 h-4 animate-ping rounded-full bg-primary-400/20" />
          </div>
          <div>
            <span className="text-sm font-semibold text-white">Buffering Ollama Response</span>
            <p className="text-[10px] text-gray-500 mt-0.5">
              {isWaitingForModel
                ? 'Waiting for Ollama to start generating...'
                : isActivelyBuffering
                  ? 'Receiving tokens from local LLM'
                  : 'Processing...'}
            </p>
          </div>
        </div>
        <button
          onClick={() => setShowDetails(!showDetails)}
          className="text-xs text-gray-500 hover:text-gray-300 px-2 py-1 rounded hover:bg-surface-700/50 transition-all"
        >
          {showDetails ? 'Hide' : 'Details'}
        </button>
      </div>

      {/* Progress Section */}
      <div className="px-4 py-3 space-y-3">
        {/* Model info */}
        <div className="flex items-center gap-2 text-xs text-gray-500">
          <Cpu className="w-3.5 h-3.5 text-primary-400" />
          <span className="text-gray-400 font-medium">{buffering.model}</span>
          <span className="text-gray-600">|</span>
          <Radio className="w-3 h-3 text-accent-400" />
          <span className="text-accent-400">{charsPerSecond} chars/s</span>
        </div>

        {/* Progress bar */}
        <div className="space-y-1.5">
          <div className="flex justify-between text-xs">
            <span className="text-gray-500">
              {isActivelyBuffering
                ? `Buffered ${buffering.charsBuffered.toLocaleString()} chars`
                : 'Connecting to Ollama...'}
            </span>
            <span className="text-gray-400 font-mono">{elapsed.toFixed(1)}s</span>
          </div>

          {/* Animated progress bar - indeterminate while waiting, determinate while buffering */}
          <div className="h-2 bg-surface-700 rounded-full overflow-hidden relative">
            {isWaitingForModel ? (
              <motion.div
                className="h-full rounded-full bg-gradient-to-r from-primary-500/40 via-primary-400 to-primary-500/40"
                animate={{ x: ['-100%', '200%'] }}
                transition={{ repeat: Infinity, duration: 1.5, ease: 'linear' }}
                style={{ width: '40%' }}
              />
            ) : (
              <motion.div
                className="h-full rounded-full bg-gradient-to-r from-primary-500 to-accent-500"
                initial={{ width: 0 }}
                animate={{
                  width: `${Math.min((buffering.charsBuffered / Math.max(buffering.charsBuffered + 100, 200)) * 100, 85)}%`,
                }}
                transition={{ duration: 0.3 }}
              />
            )}
          </div>

          {/* Speed indicator */}
          {isSlow && (
            <div className="flex items-center gap-1.5 text-[10px] text-amber-400">
              <Clock className="w-3 h-3" />
              <span>Slow response — buffering may take a moment</span>
            </div>
          )}
        </div>

        {/* Live chunks - streaming text */}
        {isActivelyBuffering && buffering.events.length > 0 && (
          <div className="pt-2 border-t border-surface-700/50">
            <div className="flex items-center gap-1.5 mb-2">
              <Sparkles className="w-3 h-3 text-primary-400" />
              <span className="text-[10px] text-gray-500 uppercase tracking-wider">Live Stream</span>
            </div>
            <div className="max-h-16 overflow-y-auto text-xs text-gray-400 font-mono leading-relaxed">
              {buffering.events
                .filter((e): e is BufferingEvent & { latest_chunk: string } =>
                  e.event === 'buffer_chunk' && !!e.latest_chunk
                )
                .slice(-5)
                .map((e, i) => (
                  <span key={i} className="text-gray-300">{e.latest_chunk}</span>
                ))}
              <span className="animate-pulse text-primary-400">▌</span>
            </div>
          </div>
        )}

        {/* Status badges */}
        <div className="flex items-center gap-2 pt-1">
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-primary-500/10 text-primary-400">
            <Zap className="w-2.5 h-2.5" />
            Ollama
          </span>
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-accent-500/10 text-accent-400">
            <Radio className="w-2.5 h-2.5" />
            {charsPerSecond} c/s
          </span>
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-amber-500/10 text-amber-400">
            <Clock className="w-2.5 h-2.5" />
            {elapsed.toFixed(1)}s
          </span>
        </div>
      </div>

      {/* Detailed log */}
      <AnimatePresence>
        {showDetails && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="border-t border-surface-700/50 overflow-hidden"
          >
            <div className="px-4 py-3 space-y-1 max-h-32 overflow-y-auto font-mono text-[10px]">
              {buffering.events.length === 0 ? (
                <div className="text-gray-600 italic">Waiting for events...</div>
              ) : (
                buffering.events.map((event, i) => (
                  <div key={i} className="flex gap-2">
                    <span className="text-gray-600 shrink-0">
                      {new Date().toLocaleTimeString()}
                    </span>
                    <span className={
                      event.event === 'buffering_start' ? 'text-primary-400' :
                      event.event === 'buffer_chunk' ? 'text-accent-400' :
                      event.event === 'buffering_done' ? 'text-emerald-400' :
                      event.event === 'buffering_error' ? 'text-red-400' :
                      'text-gray-500'
                    }>
                      [{event.event}]
                    </span>
                    <span className="text-gray-500 truncate">
                      {event.event === 'buffering_start' && `Model: ${event.model}`}
                      {event.event === 'buffer_chunk' && `${event.chars_buffered} chars`}
                      {event.event === 'buffering_done' && `${event.total_chars} total chars in ${event.elapsed_seconds}s`}
                      {event.event === 'buffering_error' && `Error: ${event.error}`}
                    </span>
                  </div>
                ))
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Completion/Error states handled by parent via AnimatePresence */}
    </motion.div>
  );
}

/**
 * Mini buffering status badge — shown in the top bar or inline.
 */
export function BufferingBadge({ buffering }: { buffering: BufferingState | null }) {
  if (!buffering || !buffering.active) return null;

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.8 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.8 }}
      className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-primary-500/10 border border-primary-500/20"
    >
      <div className="relative">
        <Loader2 className="w-3 h-3 text-primary-400 animate-spin" />
      </div>
      <span className="text-[10px] font-medium text-primary-400">
        Buffering {buffering.charsBuffered > 0 ? `${buffering.charsBuffered}c` : '...'}
      </span>
    </motion.div>
  );
}

/**
 * Hook to manage buffering state from SSE streaming.
 */
export function useBuffering() {
  const [buffering, setBuffering] = useState<BufferingState | null>(null);
  const eventsRef = useRef<BufferingEvent[]>([]);

  const startBuffering = (model: string) => {
    eventsRef.current = [];
    setBuffering({
      active: true,
      model,
      charsBuffered: 0,
      elapsedSeconds: 0,
      statusText: 'Starting...',
      events: [],
    });
  };

  const handleBufferingEvent = (event: BufferingEvent) => {
    eventsRef.current = [...eventsRef.current, event];

    if (event.event === 'buffering_start') {
      setBuffering((prev) => prev ? {
        ...prev,
        statusText: `Waiting for ${event.model}...`,
        events: eventsRef.current,
      } : null);
    } else if (event.event === 'buffer_chunk') {
      setBuffering((prev) => prev ? {
        ...prev,
        charsBuffered: event.chars_buffered ?? prev.charsBuffered,
        elapsedSeconds: event.elapsed_seconds ?? prev.elapsedSeconds,
        statusText: `Buffering from ${prev.model}...`,
        events: eventsRef.current,
      } : null);
    } else if (event.event === 'buffering_done') {
      setBuffering((prev) => prev ? {
        ...prev,
        charsBuffered: event.total_chars ?? prev.charsBuffered,
        elapsedSeconds: event.elapsed_seconds ?? prev.elapsedSeconds,
        statusText: 'Complete!',
        events: eventsRef.current,
      } : null);
    } else if (event.event === 'buffering_error') {
      setBuffering((prev) => prev ? {
        ...prev,
        statusText: `Error: ${event.error}`,
        events: eventsRef.current,
      } : null);
    }
  };

  const stopBuffering = () => {
    setBuffering(null);
    eventsRef.current = [];
  };

  return { buffering, startBuffering, handleBufferingEvent, stopBuffering };
}
