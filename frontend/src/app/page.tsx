"use client";
import { useState, useRef, useEffect } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

export default function Home() {
  const ws = useRef<WebSocket | null>(null);
  const [userInput, setUserInput] = useState<string>("");

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
  };

  return (
    <div className="w-screen h-screen min-h-screen relative">
      <div>
        <h1>orchids-challenge</h1>

        <Input
          type="text"
          value={userInput}
          onChange={(e: any) => {
            setUserInput(e.target.value);
          }}
        />
        <Button className="cursor-pointer" onClick={cloneWebsite}>
          clone.
        </Button>
      </div>
    </div>
  );
}
