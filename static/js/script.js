// Handle PDF/Word Q&A form
document.getElementById("qaForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const formData = new FormData(e.target);

    try {
        const res = await fetch("/ask", {
            method: "POST",
            body: formData,
        });

        if (!res.ok) throw new Error("Server error while getting answer.");
        const data = await res.json();
        document.getElementById("qaResult").textContent = data.answer || "No answer found.";
    } catch (err) {
        document.getElementById("qaResult").textContent = "❌ " + err.message;
    }
});

// Handle Article Summarization form
document.getElementById("summaryForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const url = e.target.url.value;

    try {
        const formData = new FormData();
        formData.append("url", url);

        const res = await fetch("/ask", {
            method: "POST",
            body: formData,
        });

        if (!res.ok) throw new Error("Server error while summarizing.");
        const data = await res.json();
        // The /ask route returns { answer } for both QA and summarization
        document.getElementById("summaryResult").textContent = data.answer || "No summary found.";
    } catch (err) {
        document.getElementById("summaryResult").textContent = "❌ " + err.message;
    }
});
