import NextAuth, { type NextAuthConfig } from "next-auth";
import Credentials from "next-auth/providers/credentials";
import Google from "next-auth/providers/google";
import { eq } from "drizzle-orm";
import bcrypt from "bcryptjs";
import { db } from "./db";
import * as schema from "./db-schema";

function adminEmails(): string[] {
  return (process.env.ADMIN_EMAILS || "")
    .split(",")
    .map((e) => e.trim().toLowerCase())
    .filter(Boolean);
}

export function isAdminEmail(email: string | null | undefined): boolean {
  return !!email && adminEmails().includes(email.toLowerCase());
}

const providers: NextAuthConfig["providers"] = [
  Credentials({
    name: "credentials",
    credentials: {
      email: { label: "Email", type: "email" },
      password: { label: "Password", type: "password" },
    },
    async authorize(credentials) {
      if (!credentials?.email || !credentials?.password) {
        return null;
      }

      const email = credentials.email as string;
      const password = credentials.password as string;

      const [user] = await db
        .select()
        .from(schema.users)
        .where(eq(schema.users.email, email))
        .limit(1);

      if (!user || !user.passwordHash) {
        return null;
      }

      const isValid = await bcrypt.compare(password, user.passwordHash);
      if (!isValid) {
        return null;
      }

      return {
        id: user.id,
        email: user.email,
        name: user.name,
        image: user.image,
      };
    },
  }),
];

if (process.env.GOOGLE_CLIENT_ID && process.env.GOOGLE_CLIENT_SECRET) {
  providers.push(
    Google({
      clientId: process.env.GOOGLE_CLIENT_ID,
      clientSecret: process.env.GOOGLE_CLIENT_SECRET,
    })
  );
}

export const { handlers, signIn, signOut, auth } = NextAuth({
  trustHost: true,
  providers,
  callbacks: {
    async signIn({ user, account, profile }) {
      // JWT sessions have no DB adapter, but shipments FK to users.id, so
      // Google sign-ins must be upserted into the users table ourselves.
      if (account?.provider === "google" && user.email) {
        const [existing] = await db
          .select()
          .from(schema.users)
          .where(eq(schema.users.email, user.email))
          .limit(1);

        if (existing) {
          user.id = existing.id;
          if (!existing.googleId && profile?.sub) {
            await db
              .update(schema.users)
              .set({ googleId: profile.sub, image: user.image ?? existing.image })
              .where(eq(schema.users.id, existing.id));
          }
        } else {
          const [created] = await db
            .insert(schema.users)
            .values({
              name: user.name || user.email,
              email: user.email,
              image: user.image,
              googleId: profile?.sub,
              emailVerified: new Date(),
            })
            .returning({ id: schema.users.id });
          user.id = created.id;
        }
      }
      return true;
    },
    async jwt({ token, user }) {
      if (user) {
        token.id = user.id;
        token.name = user.name;
      }
      return token;
    },
    async session({ session, token }) {
      if (session.user) {
        session.user.id = token.id as string;
        session.user.name = token.name as string;
        session.user.isAdmin = isAdminEmail(session.user.email);
      }
      return session;
    },
  },
  pages: {
    signIn: "/auth/signin",
    error: "/auth/signin",
  },
  session: {
    strategy: "jwt",
    maxAge: 30 * 24 * 60 * 60,
  },
});

export const { GET, POST } = handlers;

export async function getServerSession() {
  return await auth();
}

/** Returns the session if the user is an admin, otherwise null. */
export async function requireAdmin() {
  const session = await auth();
  if (!session?.user?.id || !isAdminEmail(session.user.email)) {
    return null;
  }
  return session;
}
