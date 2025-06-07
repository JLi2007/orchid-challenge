"use client";
import { useState, useRef } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import ProgressBar from "@/components/progress";

export default function Home() {
  const ws = useRef<WebSocket | null>(null);
  const [userInput, setUserInput] = useState<string>("https://www.tripadvisor.ca/");
  const [status, setStatus] = useState<
    | ""
    | "PENDING"
    | "SCRAPING"
    | "PROCESSING"
    | "GENERATING"
    | "COMPLETED"
    | "FAILED"
  >("");

  const cloneWebsite = async () => {
    console.log("cloning", userInput);

    const res = await fetch(`${process.env.NEXT_PUBLIC_BACKEND}/api/clone`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: userInput }),
    });

    const data = await res.json(); 

    console.log(data);
    const jobId = data.job_id as string;

    // ── 3. Open a single WebSocket for this job_id ──
    const backendHost = process.env.NEXT_PUBLIC_BACKEND!.replace(/^https?:\/\//, ""); 
    ws.current = new WebSocket(`ws://${backendHost}/ws/clone/${jobId}`);

    // ── 4. Handle incoming JSON messages ──
    ws.current.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data) as { status: string; progress: number };
        console.log("WS update:", msg);
        setStatus(msg.status.toUpperCase() as any);
      } catch (e) {
        console.error("WebSocket invalid JSON:", event.data, "error: ", e);
      }
    };

    ws.current.onopen = () => {
      console.log("WebSocket opened for job:", jobId);
      ws.current!.send("test");
    };
    ws.current.onclose = () => {
      console.log("WebSocket closed");
    };
    ws.current.onerror = (err) => {
      console.error("WebSocket error:", err);
    };

    // Clear any previous status/progress
    setStatus("PENDING");
  };

  return (
    <div className="w-screen h-screen min-h-screen relative bg-[url('/bg1.png')] bg-cover bg-center">
      <div className="flex w-full items-center justify-center">
        <div className="p-5 flex items-center justify-center flex-col gap-3 w-[90%] bg-pink-200/50 rounded-b-xl">
          <h1 className="text-black font-bold text-2xl">orchids-challenge</h1>

          <Input
            type="text"
            placeholder="url"
            value={userInput}
            onChange={(e: any) => {
              setUserInput(e.target.value);
            }}
            className="bg-pink-100 w-[50%]"
          />
          <Button
            className="cursor-pointer bg-pink-200/80 hover:bg-pink-200/70"
            variant={"secondary"}
            onClick={cloneWebsite}
          >
            clone.
          </Button>

          <ProgressBar status={status}/>
        </div>
      </div>

      <div className="h-auto w-full">
            {/* preview */}
      </div>
    </div>
  );
}
