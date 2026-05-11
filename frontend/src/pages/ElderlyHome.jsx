import { useState, useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { reminderAPI } from '../api';
import { Camera, Bell, CheckCircle, Clock, AlertTriangle, Volume2, X } from 'lucide-react';

export default function ElderlyHome() {
  const { user } = useAuth();
  const [todayStatus, setTodayStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showConfirmModal, setShowConfirmModal] = useState(null);
  const audioRef = useRef(null);

  useEffect(() => {
    loadTodayStatus();
  }, []);

  const loadTodayStatus = async () => {
    try {
      const res = await reminderAPI.getTodayStatus();
      setTodayStatus(res.data);
    } catch (err) {
      console.error('加载今日状态失败', err);
    } finally {
      setLoading(false);
    }
  };

  const handleConfirm = async (reminderId) => {
    try {
      await reminderAPI.confirmMedication(reminderId);
      setShowConfirmModal(null);
      loadTodayStatus();
    } catch (err) {
      alert('确认失败：' + (err.response?.data?.detail || '未知错误'));
    }
  };

  const speakWithBrowser = (text) => {
    if ('speechSynthesis' in window) {
      const u = new SpeechSynthesisUtterance(text);
      u.lang = 'zh-CN';
      u.rate = 0.8;
      speechSynthesis.speak(u);
    }
  };

  const playAudio = async (reminderId) => {
    try {
      const res = await reminderAPI.getAudio(reminderId);
      if (res.data.url && audioRef.current) {
        audioRef.current.src = res.data.url;
        audioRef.current.onerror = () => {
          if (res.data.text) speakWithBrowser(res.data.text);
        };
        audioRef.current.play().catch(() => {
          if (res.data.text) speakWithBrowser(res.data.text);
        });
      } else if (res.data.text) {
        speakWithBrowser(res.data.text);
      }
    } catch (err) {
      console.error('播放失败', err);
      const item = todayStatus?.items?.find(i => i.reminder_id === reminderId);
      if (item && 'speechSynthesis' in window) {
        const text = `吃药提醒：请在${item.reminder_time}服用${item.drug_name || '药品'}，${item.dosage || '按说明书服用'}`;
        speakWithBrowser(text);
      }
    }
  };

  const getMealText = (meal) => {
    const map = { before_meal: '饭前', after_meal: '饭后', empty_stomach: '空腹', before_sleep: '睡前' };
    return map[meal] || '';
  };

  const getStatusBadge = (status) => {
    switch (status) {
      case 'taken':
        return <span className="flex items-center gap-1 text-green-600 font-bold text-elder-base"><CheckCircle className="w-7 h-7" />已服药</span>;
      case 'late':
        return <span className="flex items-center gap-1 text-yellow-600 font-bold text-elder-base"><Clock className="w-7 h-7" />迟服</span>;
      case 'missed':
        return <span className="flex items-center gap-1 text-red-600 font-bold text-elder-base"><AlertTriangle className="w-7 h-7" />漏服</span>;
      default:
        return <span className="flex items-center gap-1 text-orange-500 font-bold text-elder-base"><Bell className="w-7 h-7" />待服药</span>;
    }
  };

  return (
    <div className="space-y-4 sm:space-y-6">
      <audio ref={audioRef} className="hidden" />

      {/* 问候语 */}
      <div className="card-elder bg-gradient-to-r from-orange-50 to-yellow-50 border-orange-200">
        <h1 className="text-2xl sm:text-elder-2xl font-bold text-gray-800">
          {user?.display_name}，您好！
        </h1>
        <p className="text-base sm:text-elder-base text-gray-600 mt-1">
          今天记得按时吃药哦
        </p>
      </div>

      {/* 快捷操作 */}
      <div className="grid grid-cols-2 gap-3 sm:gap-4">
        <Link
          to="/recognize"
          className="card-elder flex flex-col items-center justify-center py-6 sm:py-8 hover:shadow-lg transition border-orange-200 hover:border-orange-400 active:scale-95"
        >
          <Camera className="w-12 h-12 sm:w-14 sm:h-14 text-orange-500 mb-2" />
          <span className="text-lg sm:text-elder-lg font-bold text-gray-800">拍照识药</span>
          <span className="text-sm sm:text-elder-sm text-gray-500 mt-1">拍药盒自动识别</span>
        </Link>
        <Link
          to="/reminders"
          className="card-elder flex flex-col items-center justify-center py-6 sm:py-8 hover:shadow-lg transition border-blue-200 hover:border-blue-400 active:scale-95"
        >
          <Bell className="w-12 h-12 sm:w-14 sm:h-14 text-blue-500 mb-2" />
          <span className="text-lg sm:text-elder-lg font-bold text-gray-800">吃药提醒</span>
          <span className="text-sm sm:text-elder-sm text-gray-500 mt-1">查看所有提醒</span>
        </Link>
      </div>

      {/* 今日服药概览 */}
      {loading ? (
        <div className="card-elder text-center text-base sm:text-elder-base text-gray-500 py-8">加载中...</div>
      ) : todayStatus ? (
        <div className="space-y-3 sm:space-y-4">
          <h2 className="text-xl sm:text-elder-xl font-bold text-gray-800">今日服药</h2>

          {/* 统计 */}
          <div className="grid grid-cols-3 gap-2 sm:gap-3">
            <div className="card-elder text-center border-green-200 !p-3 sm:!p-4">
              <div className="text-3xl sm:text-elder-2xl font-bold text-green-600">{todayStatus.taken}</div>
              <div className="text-sm sm:text-elder-sm text-gray-500">已服药</div>
            </div>
            <div className="card-elder text-center border-orange-200 !p-3 sm:!p-4">
              <div className="text-3xl sm:text-elder-2xl font-bold text-orange-500">{todayStatus.pending}</div>
              <div className="text-sm sm:text-elder-sm text-gray-500">待服药</div>
            </div>
            <div className="card-elder text-center border-red-200 !p-3 sm:!p-4">
              <div className="text-3xl sm:text-elder-2xl font-bold text-red-500">{todayStatus.missed}</div>
              <div className="text-sm sm:text-elder-sm text-gray-500">已漏服</div>
            </div>
          </div>

          {/* 提醒列表 */}
          {todayStatus.items.length === 0 ? (
            <div className="card-elder text-center text-base sm:text-elder-base text-gray-500 py-8">
              今天还没有吃药提醒，可以先去拍照识药添加药品哦
            </div>
          ) : (
            <div className="space-y-3">
              {todayStatus.items.map((item) => (
                <div
                  key={item.reminder_id}
                  className={`card-elder ${
                    item.status === 'pending' ? 'animate-pulse-remind border-orange-300' : ''
                  } ${item.status === 'taken' ? 'border-green-200 bg-green-50/50' : ''}`}
                >
                  {/* 顶部信息行 */}
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-xl sm:text-elder-xl font-bold text-orange-600">
                      {item.reminder_time}
                    </span>
                    {getMealText(item.meal_relation) && (
                      <span className="px-2 py-0.5 bg-orange-100 text-orange-700 rounded-full text-sm font-medium">
                        {getMealText(item.meal_relation)}
                      </span>
                    )}
                    <button
                      onClick={() => playAudio(item.reminder_id)}
                      className="ml-auto p-2 bg-blue-100 text-blue-600 rounded-xl hover:bg-blue-200 transition active:scale-95"
                      aria-label="语音播报"
                    >
                      <Volume2 className="w-6 h-6 sm:w-7 sm:h-7" />
                    </button>
                  </div>

                  {/* 药品信息 */}
                  <div className="flex items-center gap-3 mb-2">
                    {item.drug_image && (
                      <img
                        src={`/uploads/${item.drug_image}`}
                        alt={item.drug_name}
                        className="w-14 h-14 sm:w-16 sm:h-16 object-cover rounded-xl border-2 border-gray-200 flex-shrink-0"
                      />
                    )}
                    <div className="flex-1 min-w-0">
                      <div className="text-lg sm:text-elder-lg font-bold text-gray-800 truncate">{item.drug_name}</div>
                      <div className="text-base sm:text-elder-base text-gray-600">{item.dosage}</div>
                    </div>
                  </div>

                  {/* 状态 + 操作按钮 */}
                  <div className="flex items-center justify-between gap-3">
                    <div>{getStatusBadge(item.status)}</div>
                    {item.status === 'pending' && (
                      <div className="flex flex-col items-end gap-2">
                        <span className="text-sm sm:text-base text-orange-700 font-medium">
                          吃完后再点确认
                        </span>
                        <button
                          onClick={() => setShowConfirmModal(item)}
                          className="px-6 py-3 bg-orange-500 text-white font-bold rounded-2xl text-lg shadow-lg active:scale-95 transition whitespace-nowrap hover:bg-orange-600"
                        >
                          去确认服药
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      ) : null}

      {showConfirmModal && (
        <div className="fixed inset-0 bg-black/50 flex items-end sm:items-center justify-center z-50">
          <div
            className="bg-white rounded-t-3xl sm:rounded-3xl p-6 sm:p-8 w-full sm:max-w-md space-y-5"
            style={{ paddingBottom: 'max(env(safe-area-inset-bottom, 16px), 24px)' }}
          >
            <div className="flex justify-between items-start">
              <h2 className="text-xl sm:text-elder-xl font-bold text-gray-800">确认服药</h2>
              <button onClick={() => setShowConfirmModal(null)} className="p-1 text-gray-400 hover:text-gray-600">
                <X className="w-7 h-7" />
              </button>
            </div>
            <div className="text-center space-y-2">
              <div className="text-xl sm:text-elder-xl font-bold text-orange-600">{showConfirmModal.drug_name}</div>
              <div className="text-lg sm:text-elder-lg text-gray-600">{showConfirmModal.reminder_time}</div>
              <div className="text-base sm:text-elder-base text-gray-500">{showConfirmModal.dosage}</div>
              {getMealText(showConfirmModal.meal_relation) && (
                <div className="text-sm sm:text-base text-orange-700 font-medium">
                  {getMealText(showConfirmModal.meal_relation)}服用
                </div>
              )}
            </div>
            <div className="grid grid-cols-2 gap-3">
              <button
                onClick={() => setShowConfirmModal(null)}
                className="py-4 bg-gray-200 text-gray-700 font-bold rounded-2xl text-lg active:scale-95"
              >
                还没吃
              </button>
              <button
                onClick={() => handleConfirm(showConfirmModal.reminder_id)}
                className="py-4 bg-green-600 text-white font-bold rounded-2xl text-lg active:scale-95 shadow-lg hover:bg-green-700"
              >
                确认已服药
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
