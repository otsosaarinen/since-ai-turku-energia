import { useCallback, useEffect, useRef, useState } from "react";
import { FRAME_INTERVAL_MS, PLAYBACK_SPEEDS } from "../constants";

const clamp = (value: number, min: number, max: number) => Math.max(min, Math.min(max, value));

/**
 * The playhead over the list of forecast origins (one per hour).
 * `playheadPosition` is fractional: the integer part is a forecast hour, the fraction the time in between. The chart slides and
 * blends the two neighbouring forecasts, so stepping and playing look smooth even though forecasts exist only once an hour.
 */
export function usePlayback(origins: string[] | null) {
  const lastIndex = origins ? origins.length - 1 : 0;
  const [playheadPosition, setPlayheadPosition] = useState(0);
  const positionRef = useRef(0);
  const targetRef = useRef(0);                       // where a glide is heading
  const [isPlaying, setIsPlaying] = useState(false);
  const isPlayingRef = useRef(false);
  const [speed, setSpeed] = useState<number>(PLAYBACK_SPEEDS[0]);   // forecast hours per second while playing
  const speedRef = useRef<number>(PLAYBACK_SPEEDS[0]);
  const [isGliding, setIsGliding] = useState(false);   // moving towards targetRef after a button click
  const shownOriginRef = useRef<string | null>(null);

  useEffect(() => { speedRef.current = speed; }, [speed]);

  const moveTo = useCallback((position: number) => {
    positionRef.current = position;
    setPlayheadPosition(position);
  }, []);

  /** Jump (or glide) to an origin by its position in the list. Stops playing. */
  const jumpTo = useCallback((originPosition: number, glide: boolean) => {
    const target = clamp(originPosition, 0, lastIndex);
    isPlayingRef.current = false;
    setIsPlaying(false);
    targetRef.current = target;
    if (glide) setIsGliding(true);
    else moveTo(target);
  }, [lastIndex, moveTo]);

  const stepBy = useCallback((hours: number) => jumpTo(Math.round(targetRef.current) + hours, true), [jumpTo]);

  const togglePlay = useCallback(() => {
    if (isPlayingRef.current) { jumpTo(Math.round(positionRef.current), true); return; }
    if (positionRef.current >= lastIndex - 0.001) moveTo(0);
    isPlayingRef.current = true;
    setIsPlaying(true);
  }, [jumpTo, lastIndex, moveTo]);

  const cycleSpeed = useCallback(() => {
    setSpeed((current) => PLAYBACK_SPEEDS[(PLAYBACK_SPEEDS.indexOf(current as (typeof PLAYBACK_SPEEDS)[number]) + 1) % PLAYBACK_SPEEDS.length]);
  }, []);

  const selectedIndex = origins ? clamp(Math.round(playheadPosition), 0, lastIndex) : 0;

  // A new forecast file: keep the hour if it exists there (input switches, method), otherwise start from the beginning.
  useEffect(() => {
    if (!origins) return;
    if (!shownOriginRef.current || origins.indexOf(shownOriginRef.current) < 0) jumpTo(0, false);
  }, [origins, jumpTo]);
  useEffect(() => { if (origins) shownOriginRef.current = origins[selectedIndex]; });

  // The animation clock only runs while playing or gliding.
  useEffect(() => {
    if (!origins || !(isPlaying || isGliding)) return undefined;
    const timer = setInterval(() => {
      let position = positionRef.current;
      if (isPlayingRef.current) {
        position += (speedRef.current * FRAME_INTERVAL_MS) / 1000;
        if (position >= lastIndex) { position = lastIndex; isPlayingRef.current = false; setIsPlaying(false); }
        targetRef.current = position;
        moveTo(position);
      } else {
        const distance = targetRef.current - position;
        if (Math.abs(distance) < 0.004) { moveTo(targetRef.current); setIsGliding(false); }
        else moveTo(position + distance * 0.28);
      }
    }, FRAME_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [origins, lastIndex, isPlaying, isGliding, moveTo]);

  return { playheadPosition, selectedIndex, lastIndex, isPlaying, speed, jumpTo, stepBy, togglePlay, cycleSpeed };
}
