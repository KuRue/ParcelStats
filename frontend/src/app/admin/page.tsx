import { requireAdmin } from "@/lib/auth";
import { redirect } from "next/navigation";
import { Navbar } from "@/components/ui/navbar";
import { AdminContent } from "@/components/admin/admin-content";

export default async function AdminPage() {
  const session = await requireAdmin();

  if (!session) {
    redirect("/dashboard");
  }

  return (
    <div className="min-h-screen">
      <Navbar />
      <AdminContent />
    </div>
  );
}
