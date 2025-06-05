"use client";
import { useState, useRef, useEffect } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import ProgressBar from "@/components/progress";

export default function Home() {
  const ws = useRef<WebSocket | null>(null);
  const [userInput, setUserInput] = useState<string>("");
  const [status, setStatus] = useState<"" | "PENDING" | "SCRAPING" | "PROCESSING" | "GENERATING" | "COMPLETED" | "FAILED">("");
  
  // websocket
  useEffect(() => {
    ws.current = new WebSocket("ws://localhost:8000/ws");

    ws.current.onmessage = (event) => {
      console.log(event);
    };

    return () => ws.current?.close();
  }, []);

  const cloneWebsite = async () => {
    console.log("cloning");
    setStatus("");
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
            className="cursor-pointer bg-pink-200 hover:bg-pink-200/50"
            variant={"secondary"}
            onClick={cloneWebsite}
          >
            clone.
          </Button>

          <ProgressBar status={status}/>
        </div>
      </div>

      <div></div>
    </div>
  );
}
