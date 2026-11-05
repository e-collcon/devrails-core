import { notFound } from "next/navigation";
import { DashboardScreen } from "@/components/dashboard/DashboardScreen";
import { FIXTURE_KEYS, getFixture } from "@/lib/feed/source";

export const dynamicParams = false;

export function generateStaticParams() {
  return FIXTURE_KEYS.map((state) => ({ state }));
}

export function generateMetadata({ params }: { params: { state: string } }) {
  return { title: `Dashboard — ${getFixture(params.state).entry.label} · DevRails` };
}

export default function DashboardStatePage({ params }: { params: { state: string } }) {
  if (!FIXTURE_KEYS.includes(params.state)) notFound();
  return <DashboardScreen fixtureKey={params.state} />;
}
