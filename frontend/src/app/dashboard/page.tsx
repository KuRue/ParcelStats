import { getServerSession } from "@/lib/auth";
import { redirect } from "next/navigation";
import { Navbar } from "@/components/ui/navbar";
import { DashboardContent } from "@/components/dashboard/dashboard-content";

export default async function DashboardPage() {
  const session = await getServerSession();

  if (!session?.user?.id) {
    redirect("/");
  }

  return (
    <div className="min-h-screen">
      <Navbar />
      <DashboardContent userId={session.user.id} />
    </div>
  );
}
