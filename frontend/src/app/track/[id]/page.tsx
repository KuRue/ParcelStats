import { getServerSession } from "@/lib/auth";
import { Navbar } from "@/components/ui/navbar";
import { TrackDetailContent } from "@/components/tracking/track-detail-content";

export default async function TrackPage({
  params,
}: {
  params: { id: string };
}) {
  const session = await getServerSession();

  return (
    <div className="min-h-screen">
      <Navbar />
      <TrackDetailContent shipmentId={params.id} authenticated={!!session} />
    </div>
  );
}
