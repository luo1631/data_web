import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import AppLayout from "./components/layout/AppLayout";
import CrawlPage from "./pages/CrawlPage";
import DataStoragePage from "./pages/DataStoragePage";
import AnalysisPage from "./pages/AnalysisPage";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppLayout />}>
          <Route path="/" element={<Navigate to="/crawl" replace />} />
          <Route path="/crawl" element={<CrawlPage />} />
          <Route path="/storage" element={<DataStoragePage />} />
          <Route path="/analysis" element={<AnalysisPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
