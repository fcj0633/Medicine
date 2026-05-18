import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { drugAPI, familyAPI, reminderAPI } from '../api';
import {
  AlertTriangle,
  Bell,
  Camera,
  Loader2,
  Save,
  Search,
  Volume2,
  Wand2,
} from 'lucide-react';

const ENRICH_FIELD_LABELS = {
  drug_name: '药品名称',
  specification: '规格',
  efficacy: '功效',
  efficacy_simple: '功效简化说明',
  usage_dosage: '用法用量',
  usage_simple: '用法用量简化说明',
  frequency: '服药频次',
  caution: '注意事项',
  caution_simple: '注意事项简化说明',
};

export default function DrugRecognize() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const fileInputRef = useRef(null);
  const isElderly = user?.role === 'elderly';

  const [mode, setMode] = useState('ocr');
  const [preview, setPreview] = useState(null);
  const [file, setFile] = useState(null);
  const [recognizing, setRecognizing] = useState(false);
  const [result, setResult] = useState(null);
  const [saving, setSaving] = useState(false);

  const [manualKeyword, setManualKeyword] = useState('');
  const [searchingCatalog, setSearchingCatalog] = useState(false);
  const [catalogResults, setCatalogResults] = useState([]);
  const [selectedCatalog, setSelectedCatalog] = useState(null);
  const [manualSaving, setManualSaving] = useState(false);

  const [savedDrug, setSavedDrug] = useState(null);
  const [autoReminders, setAutoReminders] = useState(null);
  const [elderlyList, setElderlyList] = useState([]);
  const [targetUserId, setTargetUserId] = useState(null);

  useEffect(() => {
    if (user?.role === 'family') {
      familyAPI.getMyElderly().then((res) => {
        setElderlyList(res.data || []);
        if (res.data?.length > 0) {
          setTargetUserId(res.data[0].id);
        }
      }).catch(() => {});
    }
  }, [user?.role]);

  const resetSavedState = () => {
    setSavedDrug(null);
    setAutoReminders(null);
  };

  const handleModeChange = (nextMode) => {
    setMode(nextMode);
    resetSavedState();
  };

  const getRecognizeErrorMessage = (err) => {
    const status = err.response?.status;
    const detail = err.response?.data?.detail;
    if (status === 400) return detail || '图片尺寸或格式不合法，请上传清晰的 jpg、png 或 bmp 图片。';
    if (status === 422) return detail || '没有识别到文字，请重新拍摄更清晰的药盒或说明书。';
    if (status >= 500) return detail || 'OCR 服务暂时不可用，请稍后重试。';
    return detail || '请稍后重试。';
  };

  const speakText = (text) => {
    if (!text || !('speechSynthesis' in window)) return;
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = 'zh-CN';
    utterance.rate = 0.85;
    speechSynthesis.speak(utterance);
  };

  const loadAutoReminders = async (drugId) => {
    try {
      const response = await reminderAPI.autoGenerate(drugId, targetUserId);
      setAutoReminders(response.data);
    } catch {
      setAutoReminders(null);
    }
  };

  const handleFileSelect = (event) => {
    const selectedFile = event.target.files?.[0];
    if (!selectedFile) return;

    setFile(selectedFile);
    setPreview(URL.createObjectURL(selectedFile));
    setResult(null);
    resetSavedState();
  };

  const handleRecognize = async () => {
    if (!file) return;
    setRecognizing(true);
    resetSavedState();
    try {
      const response = await drugAPI.recognize(file);
      setResult(response.data);
    } catch (error) {
      alert(`识别失败：${getRecognizeErrorMessage(error)}`);
    } finally {
      setRecognizing(false);
    }
  };

  const handleSaveRecognizedDrug = async () => {
    if (!result || !file) return;
    setSaving(true);
    try {
      const response = await drugAPI.uploadAndSave(file, targetUserId);
      setSavedDrug(response.data);
      await loadAutoReminders(response.data.id);
    } catch (error) {
      alert(`保存失败：${error.response?.data?.detail || '请稍后重试。'}`);
    } finally {
      setSaving(false);
    }
  };

  const handleSearchCatalog = async () => {
    const keyword = manualKeyword.trim();
    if (!keyword) {
      alert('请先输入药品名称。');
      return;
    }

    setSearchingCatalog(true);
    resetSavedState();
    try {
      const response = await drugAPI.searchCatalog(keyword);
      const items = response.data || [];
      setCatalogResults(items);
      setSelectedCatalog(items[0] || null);
      if (items.length === 0) {
        alert('标准库中暂未找到匹配药品，请换个名称试试。');
      }
    } catch (error) {
      alert(`查询失败：${error.response?.data?.detail || '请稍后重试。'}`);
    } finally {
      setSearchingCatalog(false);
    }
  };

  const handleSaveCatalogDrug = async () => {
    if (!selectedCatalog) return;
    setManualSaving(true);
    try {
      const response = await drugAPI.createFromCatalog({
        catalog_id: selectedCatalog.id,
        target_user_id: targetUserId,
      });
      setSavedDrug(response.data);
      await loadAutoReminders(response.data.id);
    } catch (error) {
      alert(`保存失败：${error.response?.data?.detail || '请稍后重试。'}`);
    } finally {
      setManualSaving(false);
    }
  };

  const handleCreateReminders = async () => {
    if (!autoReminders?.reminders?.length) return;
    try {
      await reminderAPI.createBatch(autoReminders.reminders);
      alert('吃药提醒已创建。');
      navigate('/reminders');
    } catch (error) {
      alert(`创建提醒失败：${error.response?.data?.detail || '请稍后重试。'}`);
    }
  };

  const renderTargetUserSelector = () => (
    user?.role === 'family' && elderlyList.length > 0 ? (
      <div className="bg-blue-50 rounded-2xl p-4 border border-blue-200">
        <label className="block font-medium text-blue-700 mb-2">为哪位老人添加药品</label>
        <select
          value={targetUserId || ''}
          onChange={(event) => setTargetUserId(Number(event.target.value))}
          className="w-full px-4 py-3 border-2 border-blue-200 rounded-xl text-lg focus:border-blue-400 focus:outline-none"
        >
          {elderlyList.map((elderly) => (
            <option key={elderly.id} value={elderly.id}>{elderly.display_name}</option>
          ))}
        </select>
      </div>
    ) : null
  );

  const renderResultCard = () => {
    if (!result) return null;

    const enrichedLabels = (result.catalog_enriched_fields || []).map(
      (field) => ENRICH_FIELD_LABELS[field] || field
    );

    return (
      <div className="space-y-4">
        <h2 className={`${isElderly ? 'text-elder-xl' : 'text-xl'} font-bold text-gray-800`}>
          识别结果
        </h2>

        {result.low_confidence && (
          <div className="card-elder border-yellow-200 bg-yellow-50/80">
            <div className="flex items-start gap-3">
              <AlertTriangle className="w-6 h-6 text-yellow-600 flex-shrink-0 mt-0.5" />
              <div>
                <div className="font-bold text-yellow-800">识别结果需要人工核对</div>
                <p className="text-yellow-700 mt-1">
                  {result.confidence_notice || '识别结果可能不够准确，请手动核对。'}
                </p>
              </div>
            </div>
          </div>
        )}

        {result.catalog_enriched && (
          <div className="card-elder border-blue-200 bg-blue-50/70">
            <div className="font-bold text-blue-800">已根据药品标准库补充信息</div>
            <p className="text-blue-700 mt-1">
              匹配药品：{result.catalog_match_name || result.drug_name}；补充字段：{enrichedLabels.join('、') || '无'}。
            </p>
          </div>
        )}

        {!result.catalog_enriched && result.catalog_match_name && (
          <div className="card-elder border-emerald-200 bg-emerald-50/70">
            <div className="font-bold text-emerald-800">已匹配到药品标准库</div>
            <p className="text-emerald-700 mt-1">
              当前 OCR 信息已经比较完整，因此没有再自动补充数据库内容。
            </p>
          </div>
        )}

        <SelectionCard
          title={result.drug_name || '未能识别药品名称'}
          subtitle={result.specification}
          category={null}
          efficacyText={result.efficacy_simple}
          usageText={result.usage_simple}
          cautionText={result.caution_simple}
          onSpeakEfficacy={() => speakText(result.efficacy_simple)}
          onSpeakUsage={() => speakText(result.usage_simple)}
          onSpeakCaution={() => speakText(result.caution_simple)}
        />

        <details className="card-elder">
          <summary className="cursor-pointer font-bold text-gray-500">查看 OCR 原文</summary>
          <pre className="mt-3 text-sm text-gray-600 whitespace-pre-wrap bg-gray-50 p-4 rounded-xl">
            {result.raw_text || '无'}
          </pre>
        </details>

        {!savedDrug && (
          <button
            onClick={handleSaveRecognizedDrug}
            disabled={saving}
            className={`w-full ${isElderly ? 'btn-elder-success' : 'px-6 py-4 bg-green-600 text-white font-bold rounded-2xl text-lg hover:bg-green-700 shadow-lg'} disabled:opacity-50 flex items-center justify-center gap-2`}
          >
            {saving ? (
              <><Loader2 className="w-6 h-6 animate-spin" />保存中...</>
            ) : (
              <><Save className="w-6 h-6" />保存药品信息</>
            )}
          </button>
        )}
      </div>
    );
  };

  const renderManualSearch = () => (
    <div className="space-y-4">
      <div className="card-elder">
        <div className="flex flex-col sm:flex-row gap-3">
          <input
            type="text"
            value={manualKeyword}
            onChange={(event) => setManualKeyword(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter') {
                event.preventDefault();
                handleSearchCatalog();
              }
            }}
            placeholder="请输入药品名称，例如：阿莫西林胶囊"
            className="flex-1 px-4 py-3 border-2 border-gray-200 rounded-xl text-base sm:text-lg focus:border-orange-400 focus:outline-none"
          />
          <button
            onClick={handleSearchCatalog}
            disabled={searchingCatalog}
            className="px-5 py-3 bg-orange-500 text-white font-bold rounded-xl hover:bg-orange-600 disabled:opacity-50 flex items-center justify-center gap-2"
          >
            {searchingCatalog ? (
              <><Loader2 className="w-5 h-5 animate-spin" />查询中</>
            ) : (
              <><Search className="w-5 h-5" />查找药品</>
            )}
          </button>
        </div>
        <p className="text-sm text-gray-500 mt-3">
          如果拍照识别不方便，也可以直接输入药名，从数据库匹配对应药品信息。
        </p>
      </div>

      {catalogResults.length > 0 && (
        <div className="card-elder">
          <div className="font-bold text-gray-700 mb-3">匹配结果</div>
          <div className="grid gap-2">
            {catalogResults.map((item) => (
              <button
                key={item.id}
                onClick={() => {
                  setSelectedCatalog(item);
                  resetSavedState();
                }}
                className={`text-left px-4 py-3 rounded-xl border-2 transition ${
                  selectedCatalog?.id === item.id
                    ? 'border-orange-400 bg-orange-50'
                    : 'border-gray-200 bg-white hover:border-orange-200'
                }`}
              >
                <div className="font-bold text-gray-800">{item.name}</div>
                <div className="text-sm text-gray-500 mt-1">
                  {[item.category, item.specification].filter(Boolean).join(' · ') || '暂无补充信息'}
                </div>
              </button>
            ))}
          </div>
        </div>
      )}

      {selectedCatalog && (
        <div className="space-y-4">
          <SelectionCard
            title={selectedCatalog.name}
            subtitle={selectedCatalog.specification}
            category={selectedCatalog.category}
            efficacyText={selectedCatalog.efficacy_simple}
            usageText={selectedCatalog.usage_simple}
            cautionText={selectedCatalog.caution_simple}
            onSpeakEfficacy={() => speakText(selectedCatalog.efficacy_simple)}
            onSpeakUsage={() => speakText(selectedCatalog.usage_simple)}
            onSpeakCaution={() => speakText(selectedCatalog.caution_simple)}
          />

          {!savedDrug && (
            <button
              onClick={handleSaveCatalogDrug}
              disabled={manualSaving}
              className={`w-full ${isElderly ? 'btn-elder-success' : 'px-6 py-4 bg-green-600 text-white font-bold rounded-2xl text-lg hover:bg-green-700 shadow-lg'} disabled:opacity-50 flex items-center justify-center gap-2`}
            >
              {manualSaving ? (
                <><Loader2 className="w-6 h-6 animate-spin" />保存中...</>
              ) : (
                <><Save className="w-6 h-6" />加入我的药品</>
              )}
            </button>
          )}
        </div>
      )}
    </div>
  );

  return (
    <div className="space-y-4 sm:space-y-6 max-w-2xl mx-auto">
      <div>
        <h1 className={`${isElderly ? 'text-2xl sm:text-elder-2xl' : 'text-xl sm:text-2xl'} font-bold text-gray-800`}>
          添加药品
        </h1>
        <p className={`${isElderly ? 'text-base sm:text-elder-base' : 'text-sm sm:text-base'} text-gray-500 mt-1`}>
          支持拍照识药，也支持手动输入药品名称，从数据库查找并加入提醒。
        </p>
      </div>

      {renderTargetUserSelector()}

      <div className="grid grid-cols-2 gap-2 p-1 bg-gray-100 rounded-2xl">
        <button
          onClick={() => handleModeChange('ocr')}
          className={`px-4 py-3 rounded-xl font-bold transition ${
            mode === 'ocr' ? 'bg-white text-orange-600 shadow' : 'text-gray-500'
          }`}
        >
          拍照识药
        </button>
        <button
          onClick={() => handleModeChange('manual')}
          className={`px-4 py-3 rounded-xl font-bold transition ${
            mode === 'manual' ? 'bg-white text-orange-600 shadow' : 'text-gray-500'
          }`}
        >
          手动录入
        </button>
      </div>

      {mode === 'ocr' ? (
        <div className="space-y-4">
          <div
            onClick={() => fileInputRef.current?.click()}
            className={`card-elder cursor-pointer hover:shadow-lg transition text-center border-dashed border-3 ${
              preview ? 'border-orange-300' : 'border-gray-300 hover:border-orange-400'
            }`}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              capture="environment"
              onChange={handleFileSelect}
              className="hidden"
            />

            {preview ? (
              <div>
                <img src={preview} alt="药品图片" className="max-h-64 mx-auto rounded-2xl shadow" />
                <p className={`${isElderly ? 'text-elder-base' : 'text-base'} text-gray-500 mt-3`}>
                  点击重新选择图片
                </p>
              </div>
            ) : (
              <div className="py-12">
                <Camera className={`${isElderly ? 'w-20 h-20' : 'w-16 h-16'} text-gray-400 mx-auto mb-4`} />
                <p className={`${isElderly ? 'text-elder-lg' : 'text-lg'} font-bold text-gray-600`}>
                  点击拍照或选择图片
                </p>
                <p className={`${isElderly ? 'text-elder-sm' : 'text-sm'} text-gray-400 mt-2`}>
                  支持药盒、药板、说明书照片
                </p>
              </div>
            )}
          </div>

          {file && !result && (
            <button
              onClick={handleRecognize}
              disabled={recognizing}
              className={`w-full ${isElderly ? 'btn-elder-primary' : 'px-6 py-4 bg-orange-500 text-white font-bold rounded-2xl text-lg hover:bg-orange-600 shadow-lg'} disabled:opacity-50 flex items-center justify-center gap-2`}
            >
              {recognizing ? (
                <><Loader2 className="w-6 h-6 animate-spin" />正在识别...</>
              ) : (
                <><Wand2 className="w-6 h-6" />开始识别</>
              )}
            </button>
          )}

          {renderResultCard()}
        </div>
      ) : (
        renderManualSearch()
      )}

      {savedDrug && (
        <div className="card-elder border-green-200 bg-green-50/50">
          <h3 className={`${isElderly ? 'text-elder-lg' : 'text-lg'} font-bold text-green-700 mb-3`}>
            药品已保存
          </h3>
          {autoReminders ? (
            <>
              <p className={`${isElderly ? 'text-elder-base' : 'text-base'} text-green-800 mb-4`}>
                {autoReminders.description}
              </p>
              <button
                onClick={handleCreateReminders}
                className={`w-full ${isElderly ? 'btn-elder-primary' : 'px-6 py-3 bg-orange-500 text-white font-bold rounded-xl text-lg hover:bg-orange-600'} flex items-center justify-center gap-2`}
              >
                <Bell className="w-6 h-6" />
                一键创建吃药提醒
              </button>
            </>
          ) : (
            <p className={`${isElderly ? 'text-elder-base' : 'text-base'} text-green-800`}>
              已加入药品列表。若需要提醒，可以稍后在药品详情页继续生成。
            </p>
          )}
        </div>
      )}
    </div>
  );
}

function SelectionCard({
  title,
  subtitle,
  category,
  efficacyText,
  usageText,
  cautionText,
  onSpeakEfficacy,
  onSpeakUsage,
  onSpeakCaution,
}) {
  return (
    <div className="space-y-4">
      <div className="card-elder border-orange-200">
        <div className="text-sm text-gray-500">药品名称</div>
        <div className="text-xl sm:text-2xl font-bold text-orange-600">{title}</div>
        <div className="text-gray-500 mt-1">
          {[category, subtitle].filter(Boolean).join(' · ') || '暂无规格信息'}
        </div>
      </div>

      {efficacyText && (
        <InfoBlock title="功效说明" content={efficacyText} colorClass="green" onSpeak={onSpeakEfficacy} />
      )}
      {usageText && (
        <InfoBlock title="用法用量" content={usageText} colorClass="blue" onSpeak={onSpeakUsage} />
      )}
      {cautionText && (
        <InfoBlock title="注意事项" content={cautionText} colorClass="red" onSpeak={onSpeakCaution} />
      )}
    </div>
  );
}

function InfoBlock({ title, content, colorClass, onSpeak }) {
  const styles = {
    green: 'bg-green-50 text-green-700 border-green-200',
    blue: 'bg-blue-50 text-blue-700 border-blue-200',
    red: 'bg-red-50 text-red-700 border-red-200',
  };

  return (
    <div className={`card-elder border ${styles[colorClass] || styles.green}`}>
      <div className="flex items-center justify-between mb-2">
        <span className="font-bold text-gray-700">{title}</span>
        <button
          onClick={onSpeak}
          className="p-2 bg-white/80 text-blue-600 rounded-xl hover:bg-white"
          aria-label={`朗读${title}`}
        >
          <Volume2 className="w-5 h-5" />
        </button>
      </div>
      <p className="font-medium">{content}</p>
    </div>
  );
}
