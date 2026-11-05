"use client";
// Shows a stored UTC timestamp in the viewer's local zone (Contract A.2 Display).
// Server render shows "HH:MM UTC"; the browser swaps in local time after mount.
import { useEffect, useState } from "react";
import { utcClock } from "@/lib/feed/format";

export function LocalTime({ iso }: { iso: string }) {
  const [text, setText] = useState(utcClock(iso));
  useEffect(() => {
    setText(new Intl.DateTimeFormat(undefined, { hour: "2-digit", minute: "2-digit", timeZoneName: "short" }).format(new Date(iso)));
  }, [iso]);
  return <time dateTime={iso}>{text}</time>;
}

/** Renders a string containing "{time}" with <LocalTime> in its place. */
export function WithTime({ text, iso }: { text: string; iso?: string }) {
  if (!iso || !text.includes("{time}")) return <>{text}</>;
  const [before, after] = text.split("{time}");
  return (
    <>
      {before}
      <LocalTime iso={iso} />
      {after}
    </>
  );
}
