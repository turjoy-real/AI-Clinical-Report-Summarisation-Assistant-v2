import { BrowserRouter, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import Library from "./pages/Library";
import Observability from "./pages/Observability";
import Workspace from "./pages/Workspace";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Library />} />
          <Route path="/workspace/:runId" element={<Workspace />} />
          <Route path="/workspace" element={<Workspace />} />
          <Route path="/observability" element={<Observability />} />
          <Route path="*" element={<Library />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
