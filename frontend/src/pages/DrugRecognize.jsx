import { useEffect, useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { drugAPI, reminderAPI, familyAPI } from '../api';
import { Camera, Volume2, Save, Wand2, Loader2, Bell, AlertTriangle } from 'lucide-react';

export default function DrugRecognize() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const fileInputRef = useRef(null);
  const isElderly = user?.role === 'elderly';

  const [preview, setPreview] = useState(null);
  const [file, setFile] = useState(null);
  const [recognizing, setRecognizing] = useState(false);
  const [result, setResult] = useState(null);
  const [saving, setSaving] = useState(false);
  const [savedDrug, setSavedDrug] = useState(null);
  const [autoReminders, setAutoReminders] = useState(null);
  const [elderlyList, setElderlyList] = useState([]);
  const [targetUserId, setTargetUserId] = useState(null);

  // 家属选择目标老人
  useEffect(() => {
    if (user?.role === 'family') {
      familyAPI.getMyElderly().then(res => {
        setElderlyList(res.data);
        if (res.data.length > 0) setTargetUserId(res.data[0].id);
      }).catch(() => {});
    }
  }, [user?.role]);

  const getRecognizeErrorMessage = (err) => {
    const status = err.response?.status;
    const detail = err.response?.data?.detail;
    if (status === 400) {
      return detail || '图片尺寸或格式不合法，请上传清晰的 jpg、png 或 bmp 图片';
    }
    if (status === 422) {
      return detail || '未识别到文字，请重新拍摄更清晰的药盒或说明书';
    }
    if (status >= 500) {
      return detail || '百度 OCR 服务异常，请稍后重试';
    }
    return detail || '请重试';
  };

  const handleFileSelect = (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    setFile(f);
    setPreview(URL.createObjectURL(f));
    setResult(null);
    setSavedDrug(null);
    setAutoReminders(null);
  };

  const handleRecognize = async () => {
    if (!file) return;
    setRecognizing(true);
    try {
      const res = await drugAPI.recognize(file);
      setResult(res.data);
    } catch (err) {
      alert('识别失败：' + getRecognizeErrorMessage(err));
    } finally {
      setRecognizing(false);
    }
  };

  const handleSave = async () => {
    if (!result || !file) return;
    setSaving(true);
    try {
      const res = await drugAPI.uploadAndSave(file, targetUserId);
      setSavedDrug(res.data);

      // 自动生成提醒建议
      try {
        const remRes = await reminderAPI.autoGenerate(res.data.id, targetUserId);
        setAutoReminders(remRes.data);
      } catch {}
    } catch (err) {
      alert('保存失败：' + (err.response?.data?.detail || '请重试'));
    } finally {
      setSaving(false);
    }
  };

  const handleCreateReminders = async () => {
    if (!autoReminders || !savedDrug) return;
    try {
      await reminderAPI.createBatch(autoReminders.reminders);
      alert('提醒已创建成功！');
      navigate('/reminders');
    } catch (err) {
      alert('创建提醒失败：' + (err.response?.data?.detail || '请重试'));
    }
  };

  const speakText = (text) => {
    if ('speechSynthesis' in window) {
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = 'zh-CN';
      utterance.rate = 0.8;
      speechSynthesis.speak(utterance);
    }
  };

  return (
    <div className="space-y-4 sm:space-y-6 max-w-2xl mx-auto">
      <div>
        <h1 className={`${isElderly ? 'text-2xl sm:text-elder-2xl' : 'text-xl sm:text-2xl'} font-bold text-gray-800`}>
          拍照识药
        </h1>
        <p className={`${isElderly ? 'text-base sm:text-elder-base' : 'text-sm sm:text-base'} text-gray-500 mt-1`}>
          拍摄药盒或说明书，系统自动识别药品信息
        </p>
      </div>

      {/* 家属选择老人 */}
      {user?.role === 'family' && elderlyList.length > 0 && (
        <div className="bg-blue-50 rounded-2xl p-4 border border-blue-200">
          <label className="block font-medium text-blue-700 mb-2">为哪位老人添加药品？</label>
          <select
            value={targetUserId || ''}
            onChange={(e) => setTargetUserId(Number(e.target.value))}
            className="w-full px-4 py-3 border-2 border-blue-200 rounded-xl text-lg focus:border-blue-400 focus:outline-none"
          >
            {elderlyList.map(e => (
              <option key={e.id} value={e.id}>{e.display_name}</option>
            ))}
          </select>
        </div>
      )}

      {/* 上传区域 */}
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

      {/* 识别按钮 */}
      {file && !result && (
        <button
          onClick={handleRecognize}
          disabled={recognizing}
          className={`w-full ${isElderly ? 'btn-elder-primary' : 'px-6 py-4 bg-orange-500 text-white font-bold rounded-2xl text-lg hover:bg-orange-600 shadow-lg'} disabled:opacity-50 flex items-center justify-center gap-2`}
        >
          {recognizing ? (
            <><Loader2 className="w-6 h-6 animate-spin" />正在识别中...</>
          ) : (
            <><Wand2 className="w-6 h-6" />开始识别</>
          )}
        </button>
      )}

      {/* 识别结果 */}
      {result && (
        <div className="space-y-4">
          <h2 className={`${isElderly ? 'text-elder-xl' : 'text-xl'} font-bold text-gray-800`}>
            🔍 识别结果
          </h2>

          {result.low_confidence && (
            <div className="card-elder border-yellow-200 bg-yellow-50/80">
              <div className="flex items-start gap-3">
                <AlertTriangle className="w-6 h-6 text-yellow-600 flex-shrink-0 mt-0.5" />
                <div>
                  <div className="font-bold text-yellow-800">识别结果需要人工核对</div>
                  <p className="text-yellow-700 mt-1">
                    {result.confidence_notice || '识别结果可能不准确，请手动核对'}
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* 药品名称 */}
          <div className="card-elder border-orange-200">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-sm text-gray-500">药品名称</div>
                <div className={`${isElderly ? 'text-elder-xl' : 'text-xl'} font-bold text-orange-600`}>
                  {result.drug_name || '未能识别'}
                </div>
                {result.specification && (
                  <div className="text-gray-500 mt-1">规格：{result.specification}</div>
                )}
              </div>
            </div>
          </div>

          {/* 功效 */}
          {(result.efficacy || result.efficacy_simple) && (
            <div className="card-elder">
              <div className="flex items-center justify-between mb-2">
                <span className="font-bold text-gray-700">💊 功效说明</span>
                {result.efficacy_simple && (
                  <button
                    onClick={() => speakText(result.efficacy_simple)}
                    className="p-2 bg-blue-100 text-blue-600 rounded-xl hover:bg-blue-200"
                    aria-label="朗读功效"
                  >
                    <Volume2 className="w-6 h-6" />
                  </button>
                )}
              </div>
              {result.efficacy && (
                <p className="text-gray-600 text-sm mb-2">
                  <span className="text-gray-400">原文：</span>{result.efficacy}
                </p>
              )}
              {result.efficacy_simple && (
                <p className={`${isElderly ? 'text-elder-base' : 'text-lg'} text-green-700 bg-green-50 p-3 rounded-xl font-medium`}>
                  {result.efficacy_simple}
                </p>
              )}
            </div>
          )}

          {/* 用法用量 */}
          {(result.usage_dosage || result.usage_simple) && (
            <div className="card-elder">
              <div className="flex items-center justify-between mb-2">
                <span className="font-bold text-gray-700">📋 用法用量</span>
                {result.usage_simple && (
                  <button
                    onClick={() => speakText(result.usage_simple)}
                    className="p-2 bg-blue-100 text-blue-600 rounded-xl hover:bg-blue-200"
                    aria-label="朗读用法"
                  >
                    <Volume2 className="w-6 h-6" />
                  </button>
                )}
              </div>
              {result.usage_dosage && (
                <p className="text-gray-600 text-sm mb-2">
                  <span className="text-gray-400">原文：</span>{result.usage_dosage}
                </p>
              )}
              {result.usage_simple && (
                <p className={`${isElderly ? 'text-elder-base' : 'text-lg'} text-blue-700 bg-blue-50 p-3 rounded-xl font-medium`}>
                  {result.usage_simple}
                </p>
              )}
            </div>
          )}

          {/* 注意事项 */}
          {(result.caution || result.caution_simple) && (
            <div className="card-elder border-red-200">
              <div className="flex items-center justify-between mb-2">
                <span className="font-bold text-gray-700">⚠️ 注意事项</span>
                {result.caution_simple && (
                  <button
                    onClick={() => speakText(result.caution_simple)}
                    className="p-2 bg-blue-100 text-blue-600 rounded-xl hover:bg-blue-200"
                    aria-label="朗读注意事项"
                  >
                    <Volume2 className="w-6 h-6" />
                  </button>
                )}
              </div>
              {result.caution_simple && (
                <p className={`${isElderly ? 'text-elder-base' : 'text-lg'} text-red-700 bg-red-50 p-3 rounded-xl font-medium`}>
                  {result.caution_simple}
                </p>
              )}
            </div>
          )}

          {/* OCR 原文 */}
          <details className="card-elder">
            <summary className="cursor-pointer font-bold text-gray-500">查看 OCR 识别原文</summary>
            <pre className="mt-3 text-sm text-gray-600 whitespace-pre-wrap bg-gray-50 p-4 rounded-xl">
              {result.raw_text || '无'}
            </pre>
          </details>

          {/* 保存按钮 */}
          {!savedDrug && (
            <button
              onClick={handleSave}
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

          {/* 自动提醒建议 */}
          {autoReminders && (
            <div className="card-elder border-green-200 bg-green-50/50">
              <h3 className={`${isElderly ? 'text-elder-lg' : 'text-lg'} font-bold text-green-700 mb-3`}>
                ⏰ 自动生成提醒建议
              </h3>
              <p className={`${isElderly ? 'text-elder-base' : 'text-base'} text-green-800 mb-4`}>
                {autoReminders.description}
              </p>
              <button
                onClick={handleCreateReminders}
                className={`w-full ${isElderly ? 'btn-elder-primary' : 'px-6 py-3 bg-orange-500 text-white font-bold rounded-xl text-lg hover:bg-orange-600'} flex items-center justify-center gap-2`}
              >
                <Bell className="w-6 h-6" />
                一键创建提醒
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
