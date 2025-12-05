// utils/fileHandling.ts
export const readFileAsText = (file: File): Promise<string> => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      try {
        const result = reader.result;
        if (typeof result === "string" && result.length > 0) {
          resolve(result);
        } else {
          reject(new Error("Empty or invalid text file"));
        }
      } catch (e) {
        reject(e);
      }
    };
    reader.onerror = reject;
    reader.readAsText(file);
  });
};

export const readFileAsBase64 = (file: File): Promise<string> => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      try {
        const base64 = (reader.result as string).split(",")[1];
        resolve(base64);
      } catch (e) {
        reject(e);
      }
    };
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
};

export const readFileAsPDFText = async (file: File): Promise<string> => {
  return new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = "//cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js";

    script.onload = async () => {
      try {
        // @ts-ignore - PDF.js adds this to window
        const pdfjsLib = window["pdfjs-dist/build/pdf"];
        pdfjsLib.GlobalWorkerOptions.workerSrc =
          "//cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js";

        const arrayBuffer = await file.arrayBuffer();
        const pdf = await pdfjsLib.getDocument({ data: arrayBuffer }).promise;

        let fullText = "";

        for (let i = 1; i <= pdf.numPages; i++) {
          const page = await pdf.getPage(i);
          const textContent = await page.getTextContent();

          let lastY: number | null = null;
          let text = "";

          for (const item of textContent.items) {
            if (lastY !== null && Math.abs(lastY - item.transform[5]) > 5) {
              text += "\n";
            } else if (lastY !== null && text.length > 0) {
              text += " ";
            }

            text += item.str;
            lastY = item.transform[5];
          }

          fullText += text + "\n\n";
        }

        document.body.removeChild(script);
        resolve(fullText.trim());
      } catch (error) {
        document.body.removeChild(script);
        reject(error);
      }
    };

    script.onerror = () => {
      document.body.removeChild(script);
      reject(new Error("Failed to load PDF.js library"));
    };

    document.body.appendChild(script);
  });
};

// Update the type definition
export interface FileUpload {
  base64: string;
  fileName: string;
  mediaType: string;
  isText?: boolean;
  fileSize?: number; // Optional: Add file size information
}
