import React, { useState } from "react";
import { useNavigate } from "react-router-dom";

type TrainingConfig = {
  modelType: "yolo" | "custom";
  modelVariant: "n" | "s" | "m" | "l" | "x";
  datasetFormat: "coco" | "yolo" | "pascal_voc";
  epochs: number;
  batchSize: number;
  imgSize: number;
  learningRate: number;
  trainSplit: number;
  valSplit: number;
  testSplit: number;
  modelName: string;
  description: string;
  augment: boolean;
  patience: number;
  optimizer: "SGD" | "Adam" | "AdamW" | "NAdam" | "RAdam";
  cosLr: boolean;
  multiScale: boolean;
};

type TrainingStatus = {
  status: "idle" | "preparing" | "training" | "completed" | "failed";
  progress: number;
  epoch: number;
  totalEpochs: number;
  loss: number;
  metrics: {
    precision?: number;
    recall?: number;
    mAP?: number;
  };
  message: string;
};

export default function TrainModel() {
  const nav = useNavigate();
  const [step, setStep] = useState<"upload" | "config" | "train">("upload");
  const [datasetFiles, setDatasetFiles] = useState<File[]>([]);
  const [annotationFiles, setAnnotationFiles] = useState<File[]>([]);
  const [config, setConfig] = useState<TrainingConfig>({
    modelType: "yolo",
    modelVariant: "n",
    datasetFormat: "coco",
    epochs: 100,
    batchSize: 16,
    imgSize: 640,
    learningRate: 0.01,
    trainSplit: 70,
    valSplit: 20,
    testSplit: 10,
    modelName: "",
    description: "",
    augment: true,
    patience: 50,
    optimizer: "AdamW",
    cosLr: false,
    multiScale: false,
  });
  const [trainingStatus, setTrainingStatus] = useState<TrainingStatus>({
    status: "idle",
    progress: 0,
    epoch: 0,
    totalEpochs: 0,
    loss: 0,
    metrics: {},
    message: "",
  });
  const [training, setTraining] = useState(false);

  const handleDatasetUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    const images = files.filter(f => /\.(jpg|jpeg|png|bmp)$/i.test(f.name));
    setDatasetFiles(prev => [...prev, ...images]);
  };

  const handleAnnotationUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    const annotations = files.filter(f => /\.(json|xml|txt)$/i.test(f.name));
    setAnnotationFiles(prev => [...prev, ...annotations]);
  };

  const validateDataset = () => {
    if (datasetFiles.length === 0) {
      alert("Please upload at least one image file");
      return false;
    }
    if (config.datasetFormat === "coco" && annotationFiles.length === 0) {
      alert("Please upload COCO annotation JSON file");
      return false;
    }
    if (config.modelName.trim() === "") {
      alert("Please enter a model name");
      return false;
    }
    if (config.trainSplit + config.valSplit + config.testSplit !== 100) {
      alert("Train/Val/Test splits must sum to 100%");
      return false;
    }
    return true;
  };

  const startTraining = async () => {
    if (!validateDataset()) return;

    setTraining(true);
    setStep("train");
    setTrainingStatus({
      status: "preparing",
      progress: 0,
      epoch: 0,
      totalEpochs: config.epochs,
      loss: 0,
      metrics: {},
      message: "Preparing dataset...",
    });

    try {
      // Create FormData for upload
      const formData = new FormData();
      datasetFiles.forEach((file, i) => {
        formData.append(`images`, file);
      });
      annotationFiles.forEach((file) => {
        formData.append(`annotations`, file);
      });
      formData.append("config", JSON.stringify(config));

      // Start training via API
      const response = await fetch("http://localhost:8080/api/training/start", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error("Failed to start training");
      }

      // Poll for training status
      const pollInterval = setInterval(async () => {
        try {
          const statusRes = await fetch(`http://localhost:8080/api/training/status/${config.modelName}`);
          if (statusRes.ok) {
            const status = await statusRes.json();
            setTrainingStatus(status);
            
            if (status.status === "completed" || status.status === "failed") {
              clearInterval(pollInterval);
              setTraining(false);
            }
          }
        } catch (e) {
          console.error("Failed to fetch training status:", e);
        }
      }, 2000);

    } catch (e: any) {
      alert(`Training failed: ${e.message}`);
      setTraining(false);
      setTrainingStatus(prev => ({ ...prev, status: "failed", message: e.message }));
    }
  };

  return (
    <div className="space-y-6">
      <div className="glass rounded-2xl border border-neutral-800 p-5 shadow-premium">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="text-sm text-neutral-400">Model Training</div>
            <div className="mt-1 text-xl font-semibold text-white">Train Your Own Model</div>
            <div className="mt-2 text-sm text-neutral-300">
              Upload your dataset, configure training parameters, and train a custom model for power line inspection.
            </div>
          </div>
        </div>
      </div>

      {/* Progress Steps */}
      <div className="glass rounded-2xl border border-neutral-800 p-5 shadow-premium">
        <div className="flex items-center justify-between">
          {[
            { id: "upload", label: "Upload Dataset", active: step === "upload" },
            { id: "config", label: "Configure", active: step === "config" },
            { id: "train", label: "Train", active: step === "train" },
          ].map((s, i) => (
            <React.Fragment key={s.id}>
              <div className="flex items-center gap-2">
                <div
                  className={`w-10 h-10 rounded-full flex items-center justify-center font-semibold ${
                    s.active
                      ? "bg-gradient-accent text-white"
                      : step === "train" && i < 2
                      ? "bg-premium-success text-white"
                      : "bg-premium-card border border-neutral-700 text-neutral-400"
                  }`}
                >
                  {step === "train" && i < 2 ? "✓" : i + 1}
                </div>
                <span className={`text-sm font-semibold ${s.active ? "text-white" : "text-neutral-400"}`}>
                  {s.label}
                </span>
              </div>
              {i < 2 && <div className="flex-1 h-0.5 bg-neutral-800 mx-4" />}
            </React.Fragment>
          ))}
        </div>
      </div>

      {/* Step 1: Upload Dataset */}
      {step === "upload" && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="glass rounded-2xl border border-neutral-800 p-5 shadow-premium">
            <div className="font-semibold text-white mb-4">Upload Images</div>
            <input
              type="file"
              accept="image/*"
              multiple
              onChange={handleDatasetUpload}
              className="hidden"
              id="dataset-upload"
            />
            <label
              htmlFor="dataset-upload"
              className="block w-full rounded-xl border-2 border-dashed border-neutral-700 p-8 text-center cursor-pointer hover:border-premium-accent transition-colors"
            >
              <div className="text-neutral-400 mb-2">Click to upload or drag and drop</div>
              <div className="text-sm text-neutral-500">JPG, PNG, BMP images</div>
              <div className="mt-4 text-premium-accent font-semibold">
                {datasetFiles.length} file{datasetFiles.length !== 1 ? "s" : ""} selected
              </div>
            </label>
            {datasetFiles.length > 0 && (
              <div className="mt-4 max-h-48 overflow-y-auto space-y-2">
                {datasetFiles.slice(0, 10).map((f, i) => (
                  <div key={i} className="text-xs text-neutral-400 truncate">{f.name}</div>
                ))}
                {datasetFiles.length > 10 && (
                  <div className="text-xs text-neutral-500">... and {datasetFiles.length - 10} more</div>
                )}
              </div>
            )}
          </div>

          <div className="glass rounded-2xl border border-neutral-800 p-5 shadow-premium">
            <div className="font-semibold text-white mb-4">Upload Annotations</div>
            <div className="mb-3">
              <select
                value={config.datasetFormat}
                onChange={(e) => setConfig(prev => ({ ...prev, datasetFormat: e.target.value as any }))}
                className="w-full rounded-xl bg-premium-card border border-neutral-700 text-white px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-premium-accent"
              >
                <option value="coco">COCO Format (JSON)</option>
                <option value="yolo">YOLO Format (TXT)</option>
                <option value="pascal_voc">Pascal VOC (XML)</option>
              </select>
            </div>
            <input
              type="file"
              accept={config.datasetFormat === "coco" ? ".json" : config.datasetFormat === "yolo" ? ".txt" : ".xml"}
              multiple={config.datasetFormat !== "coco"}
              onChange={handleAnnotationUpload}
              className="hidden"
              id="annotation-upload"
            />
            <label
              htmlFor="annotation-upload"
              className="block w-full rounded-xl border-2 border-dashed border-neutral-700 p-8 text-center cursor-pointer hover:border-premium-accent transition-colors"
            >
              <div className="text-neutral-400 mb-2">Click to upload annotations</div>
              <div className="text-sm text-neutral-500">
                {config.datasetFormat === "coco" && "COCO JSON file"}
                {config.datasetFormat === "yolo" && "YOLO TXT files"}
                {config.datasetFormat === "pascal_voc" && "Pascal VOC XML files"}
              </div>
              <div className="mt-4 text-premium-accent font-semibold">
                {annotationFiles.length} file{annotationFiles.length !== 1 ? "s" : ""} selected
              </div>
            </label>
            {annotationFiles.length > 0 && (
              <div className="mt-4 max-h-48 overflow-y-auto space-y-2">
                {annotationFiles.slice(0, 10).map((f, i) => (
                  <div key={i} className="text-xs text-neutral-400 truncate">{f.name}</div>
                ))}
                {annotationFiles.length > 10 && (
                  <div className="text-xs text-neutral-500">... and {annotationFiles.length - 10} more</div>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Step 2: Configuration */}
      {step === "config" && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="glass rounded-2xl border border-neutral-800 p-5 shadow-premium space-y-4">
            <div className="font-semibold text-white">Model Configuration</div>
            
            <div>
              <label className="text-sm font-medium text-white mb-2 block">Model Type</label>
              <select
                value={config.modelType}
                onChange={(e) => setConfig(prev => ({ ...prev, modelType: e.target.value as any }))}
                className="w-full rounded-xl bg-premium-card border border-neutral-700 text-white px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-premium-accent"
              >
                <option value="yolo">YOLOv8 (Recommended)</option>
                <option value="custom">Custom Architecture</option>
              </select>
            </div>

            {config.modelType === "yolo" && (
              <div>
                <label className="text-sm font-medium text-white mb-2 block">YOLOv8 Variant</label>
                <select
                  value={config.modelVariant}
                  onChange={(e) => setConfig(prev => ({ ...prev, modelVariant: e.target.value as any }))}
                  className="w-full rounded-xl bg-premium-card border border-neutral-700 text-white px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-premium-accent"
                >
                  <option value="n">YOLOv8n (Nano) - Fastest, smallest</option>
                  <option value="s">YOLOv8s (Small) - Balanced</option>
                  <option value="m">YOLOv8m (Medium) - Better accuracy</option>
                  <option value="l">YOLOv8l (Large) - High accuracy</option>
                  <option value="x">YOLOv8x (XLarge) - Best accuracy</option>
                </select>
                <div className="mt-1 text-xs text-neutral-400">
                  {config.modelVariant === "n" && "~6M params, fastest inference"}
                  {config.modelVariant === "s" && "~11M params, good balance"}
                  {config.modelVariant === "m" && "~26M params, better accuracy"}
                  {config.modelVariant === "l" && "~44M params, high accuracy"}
                  {config.modelVariant === "x" && "~68M params, best accuracy"}
                </div>
              </div>
            )}

            <div>
              <label className="text-sm font-medium text-white mb-2 block">Model Name</label>
              <input
                type="text"
                value={config.modelName}
                onChange={(e) => setConfig(prev => ({ ...prev, modelName: e.target.value }))}
                placeholder="my_custom_model_v1"
                className="w-full rounded-xl bg-premium-card border border-neutral-700 text-white placeholder-neutral-500 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-premium-accent"
              />
            </div>

            <div>
              <label className="text-sm font-medium text-white mb-2 block">Description</label>
              <textarea
                value={config.description}
                onChange={(e) => setConfig(prev => ({ ...prev, description: e.target.value }))}
                placeholder="Model description and notes..."
                rows={3}
                className="w-full rounded-xl bg-premium-card border border-neutral-700 text-white placeholder-neutral-500 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-premium-accent"
              />
            </div>
          </div>

          <div className="glass rounded-2xl border border-neutral-800 p-5 shadow-premium space-y-4">
            <div className="font-semibold text-white">Training Parameters</div>
            
            <div>
              <label className="text-sm font-medium text-white mb-2 block">
                Epochs: {config.epochs}
              </label>
              <input
                type="range"
                min="10"
                max="500"
                step="10"
                value={config.epochs}
                onChange={(e) => setConfig(prev => ({ ...prev, epochs: parseInt(e.target.value) }))}
                className="w-full"
              />
            </div>

            <div>
              <label className="text-sm font-medium text-white mb-2 block">
                Batch Size: {config.batchSize}
              </label>
              <input
                type="range"
                min="4"
                max="64"
                step="4"
                value={config.batchSize}
                onChange={(e) => setConfig(prev => ({ ...prev, batchSize: parseInt(e.target.value) }))}
                className="w-full"
              />
            </div>

            <div>
              <label className="text-sm font-medium text-white mb-2 block">
                Image Size: {config.imgSize}px
              </label>
              <input
                type="range"
                min="320"
                max="1280"
                step="32"
                value={config.imgSize}
                onChange={(e) => setConfig(prev => ({ ...prev, imgSize: parseInt(e.target.value) }))}
                className="w-full"
              />
            </div>

            <div>
              <label className="text-sm font-medium text-white mb-2 block">
                Learning Rate: {config.learningRate}
              </label>
              <input
                type="range"
                min="0.0001"
                max="0.1"
                step="0.0001"
                value={config.learningRate}
                onChange={(e) => setConfig(prev => ({ ...prev, learningRate: parseFloat(e.target.value) }))}
                className="w-full"
              />
            </div>

            <div className="grid grid-cols-3 gap-3">
              <div>
                <label className="text-sm font-medium text-white mb-2 block">Train %</label>
                <input
                  type="number"
                  min="0"
                  max="100"
                  value={config.trainSplit}
                  onChange={(e) => {
                    const val = parseInt(e.target.value);
                    const remaining = 100 - val;
                    setConfig(prev => ({
                      ...prev,
                      trainSplit: val,
                      valSplit: Math.floor(remaining * 0.67),
                      testSplit: Math.ceil(remaining * 0.33),
                    }));
                  }}
                  className="w-full rounded-xl bg-premium-card border border-neutral-700 text-white px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-premium-accent"
                />
              </div>
              <div>
                <label className="text-sm font-medium text-white mb-2 block">Val %</label>
                <input
                  type="number"
                  min="0"
                  max="100"
                  value={config.valSplit}
                  onChange={(e) => {
                    const val = parseInt(e.target.value);
                    const remaining = 100 - config.trainSplit - val;
                    setConfig(prev => ({
                      ...prev,
                      valSplit: val,
                      testSplit: Math.max(0, remaining),
                    }));
                  }}
                  className="w-full rounded-xl bg-premium-card border border-neutral-700 text-white px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-premium-accent"
                />
              </div>
              <div>
                <label className="text-sm font-medium text-white mb-2 block">Test %</label>
                <input
                  type="number"
                  min="0"
                  max="100"
                  value={config.testSplit}
                  onChange={(e) => {
                    const val = parseInt(e.target.value);
                    const remaining = 100 - config.trainSplit - val;
                    setConfig(prev => ({
                      ...prev,
                      testSplit: val,
                      valSplit: Math.max(0, remaining),
                    }));
                  }}
                  className="w-full rounded-xl bg-premium-card border border-neutral-700 text-white px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-premium-accent"
                />
              </div>
            </div>
          </div>

          <div className="glass rounded-2xl border border-neutral-800 p-5 shadow-premium space-y-4">
            <div className="font-semibold text-white">Advanced Options</div>
            
            <div className="space-y-3">
              <label className="flex items-center gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={config.augment}
                  onChange={(e) => setConfig(prev => ({ ...prev, augment: e.target.checked }))}
                  className="rounded border-neutral-600 bg-premium-card text-premium-accent focus:ring-premium-accent"
                />
                <span className="text-sm text-white">Enable Data Augmentation</span>
              </label>
              <div className="text-xs text-neutral-400 ml-7">
                Random flips, rotations, color jitter, mosaic, etc.
              </div>

              <div>
                <label className="text-sm font-medium text-white mb-2 block">
                  Optimizer: {config.optimizer}
                </label>
                <select
                  value={config.optimizer}
                  onChange={(e) => setConfig(prev => ({ ...prev, optimizer: e.target.value as any }))}
                  className="w-full rounded-xl bg-premium-card border border-neutral-700 text-white px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-premium-accent"
                >
                  <option value="SGD">SGD - Stochastic Gradient Descent</option>
                  <option value="Adam">Adam - Adaptive Moment Estimation</option>
                  <option value="AdamW">AdamW - Adam with Weight Decay (Recommended)</option>
                  <option value="NAdam">NAdam - Nesterov Adam</option>
                  <option value="RAdam">RAdam - Rectified Adam</option>
                </select>
              </div>

              <div>
                <label className="text-sm font-medium text-white mb-2 block">
                  Early Stopping Patience: {config.patience}
                </label>
                <input
                  type="range"
                  min="10"
                  max="100"
                  step="10"
                  value={config.patience}
                  onChange={(e) => setConfig(prev => ({ ...prev, patience: parseInt(e.target.value) }))}
                  className="w-full"
                />
                <div className="text-xs text-neutral-400 mt-1">
                  Stop training if no improvement for N epochs
                </div>
              </div>

              <label className="flex items-center gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={config.cosLr}
                  onChange={(e) => setConfig(prev => ({ ...prev, cosLr: e.target.checked }))}
                  className="rounded border-neutral-600 bg-premium-card text-premium-accent focus:ring-premium-accent"
                />
                <span className="text-sm text-white">Cosine Learning Rate Schedule</span>
              </label>

              <label className="flex items-center gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={config.multiScale}
                  onChange={(e) => setConfig(prev => ({ ...prev, multiScale: e.target.checked }))}
                  className="rounded border-neutral-600 bg-premium-card text-premium-accent focus:ring-premium-accent"
                />
                <span className="text-sm text-white">Multi-Scale Training</span>
              </label>
              <div className="text-xs text-neutral-400 ml-7">
                Train on multiple image sizes for better generalization
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Step 3: Training */}
      {step === "train" && (
        <div className="glass rounded-2xl border border-neutral-800 p-5 shadow-premium">
          <div className="font-semibold text-white mb-4">Training Progress</div>
          
          {trainingStatus.status === "idle" ? (
            <div className="text-center py-8 text-neutral-400">
              Click "Start Training" to begin
            </div>
          ) : (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-sm text-neutral-300">{trainingStatus.message}</span>
                <span className="text-sm font-semibold text-white">
                  {trainingStatus.status === "training" && `${trainingStatus.epoch}/${trainingStatus.totalEpochs} epochs`}
                </span>
              </div>
              
              <div className="w-full bg-neutral-800 rounded-full h-4 overflow-hidden">
                <div
                  className="bg-gradient-accent h-full transition-all duration-300"
                  style={{ width: `${trainingStatus.progress}%` }}
                />
              </div>

              {trainingStatus.status === "training" && (
                <div className="grid grid-cols-3 gap-4 text-sm">
                  <div>
                    <div className="text-neutral-400">Loss</div>
                    <div className="text-white font-semibold">{trainingStatus.loss.toFixed(4)}</div>
                  </div>
                  {trainingStatus.metrics.precision && (
                    <div>
                      <div className="text-neutral-400">Precision</div>
                      <div className="text-white font-semibold">{(trainingStatus.metrics.precision * 100).toFixed(2)}%</div>
                    </div>
                  )}
                  {trainingStatus.metrics.mAP50 && (
                    <div>
                      <div className="text-neutral-400">mAP@0.5</div>
                      <div className="text-white font-semibold">{(trainingStatus.metrics.mAP50 * 100).toFixed(2)}%</div>
                    </div>
                  )}
                  {trainingStatus.metrics['mAP50-95'] && (
                    <div>
                      <div className="text-neutral-400">mAP@0.5:0.95</div>
                      <div className="text-white font-semibold">{(trainingStatus.metrics['mAP50-95'] * 100).toFixed(2)}%</div>
                    </div>
                  )}
                </div>
              )}

              {trainingStatus.status === "completed" && (
                <div className="rounded-xl bg-premium-success/20 border border-premium-success/50 p-4 text-premium-success">
                  <div className="font-semibold">Training completed successfully!</div>
                  <div className="text-sm mt-2">Model saved and ready to use.</div>
                </div>
              )}

              {trainingStatus.status === "failed" && (
                <div className="rounded-xl bg-premium-danger/20 border border-premium-danger/50 p-4 text-premium-danger">
                  <div className="font-semibold">Training failed</div>
                  <div className="text-sm mt-2">{trainingStatus.message}</div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Navigation Buttons */}
      <div className="flex items-center justify-between">
        <button
          onClick={() => {
            if (step === "config") setStep("upload");
            else if (step === "train") setStep("config");
          }}
          disabled={step === "upload"}
          className="rounded-xl glass border border-neutral-700 text-white px-4 py-2 text-sm font-semibold hover:bg-premium-card-hover disabled:opacity-50 transition-colors"
        >
          Previous
        </button>
        <div className="flex gap-3">
          {step === "upload" && (
            <button
              onClick={() => setStep("config")}
              disabled={datasetFiles.length === 0}
              className="rounded-xl bg-gradient-accent text-white px-4 py-2 text-sm font-semibold hover:shadow-glow disabled:opacity-50 transition-all"
            >
              Next: Configure
            </button>
          )}
          {step === "config" && (
            <button
              onClick={() => setStep("train")}
              disabled={!validateDataset()}
              className="rounded-xl bg-gradient-accent text-white px-4 py-2 text-sm font-semibold hover:shadow-glow disabled:opacity-50 transition-all"
            >
              Next: Review
            </button>
          )}
          {step === "train" && (
            <button
              onClick={startTraining}
              disabled={training || !validateDataset()}
              className="rounded-xl bg-gradient-accent text-white px-4 py-2 text-sm font-semibold hover:shadow-glow disabled:opacity-50 transition-all"
            >
              {training ? "Training..." : "Start Training"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

