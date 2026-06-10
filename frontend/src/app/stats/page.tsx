import { Navbar } from "@/components/ui/navbar";
import { StatsContent } from "@/components/charts/stats-content";

export default function StatsPage() {
  return (
    <div className="min-h-screen">
      <Navbar />
      <StatsContent />
    </div>
  );
}
