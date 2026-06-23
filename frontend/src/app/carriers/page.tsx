import { getServerSession } from "@/lib/auth";
import { redirect } from "next/navigation";
import { Navbar } from "@/components/ui/navbar";
import { CarrierStatsContent } from "@/components/carriers/carrier-stats-content";

export default async function CarriersPage() {
  const session = await getServerSession();
  if (!session?.user?.id) {
    redirect("/");
  }
  return (
    <div className="min-h-screen">
      <Navbar />
      <CarrierStatsContent />
    </div>
  );
}
