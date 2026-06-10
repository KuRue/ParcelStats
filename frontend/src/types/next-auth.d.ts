export type { DefaultSession } from "next-auth";

declare module "next-auth" {
  interface Session {
    user: {
      id: string;
      email: string;
      name: string;
      image?: string | null;
      isAdmin?: boolean;
    };
  }

  interface User {
    id: string;
  }
}

declare module "@auth/drizzle-adapter" {
  interface AdapterUser {
    id: string;
    name: string;
    email: string;
    image?: string | null;
    emailVerified?: Date | null;
  }
}
