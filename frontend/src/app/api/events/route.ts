import { getServerSession } from "@/lib/auth";
import { getRedisSub, globalChannel, userChannel } from "@/lib/redis";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const session = await getServerSession();
  if (!session?.user?.id) {
    return new Response("Unauthorized", { status: 401 });
  }

  const userId = session.user.id;

  const responseHeaders = new Headers({
    "Content-Type": "text/event-stream",
    "Cache-Control": "no-cache",
    Connection: "keep-alive",
    "X-Accel-Buffering": "no",
  });

  const stream = new ReadableStream({
    start(controller) {
      const encoder = new TextEncoder();

      function send(event: string, data: unknown) {
        try {
          controller.enqueue(
            encoder.encode(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`)
          );
        } catch {}
      }

      send("connected", { user_id: userId, timestamp: new Date().toISOString() });

      const heartbeat = setInterval(() => {
        send("heartbeat", { timestamp: new Date().toISOString() });
      }, 30000);

      const redis = getRedisSub();
      const channels = [userChannel(userId), globalChannel];

      redis.subscribe(...channels).catch(() => {});

      const messageHandler = (channel: string, message: string) => {
        try {
          const event = JSON.parse(message);
          send("update", event);
        } catch {}
      };

      redis.on("message", messageHandler);

      request.signal.addEventListener("abort", () => {
        clearInterval(heartbeat);
        redis.off("message", messageHandler);
        redis.unsubscribe(...channels).catch(() => {});
        try {
          controller.close();
        } catch {}
      });
    },
  });

  return new Response(stream, { headers: responseHeaders });
}
