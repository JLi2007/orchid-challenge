// Fixed typing and basic UI
type StatusType = {
  status: "" | "PENDING" | "SCRAPING" | "PROCESSING" | "GENERATING" | "COMPLETED" | "FAILED";
};

export default function ProgressBar({ status }: StatusType) {
  const progressMap: Record<string, number> = {
    "": 0,
    PENDING: 10,
    SCRAPING: 30,
    PROCESSING: 50,
    GENERATING: 75,
    COMPLETED: 100,
    FAILED: 100,
  };

  const progress = progressMap[status] || 0;

//   placholder
  return (
    <div className="w-full max-w-md">
      <p className="mb-1 text-sm font-medium">{status}</p>
      <div className="w-full bg-gray-200 rounded-full h-4">
        <div
          className={`h-4 rounded-full ${
            status === "FAILED" ? "bg-red-500" : "bg-blue-600"
          }`}
          style={{ width: `${progress}%` }}
        ></div>
      </div>
    </div>
  );
}
