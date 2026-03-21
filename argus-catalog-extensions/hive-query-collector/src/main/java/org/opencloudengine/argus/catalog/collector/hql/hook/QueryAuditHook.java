package org.opencloudengine.argus.catalog.collector.hql.hook;

import org.apache.hadoop.hive.conf.HiveConf;
import org.apache.hadoop.hive.ql.QueryPlan;
import org.apache.hadoop.hive.ql.hooks.ExecuteWithHookContext;
import org.apache.hadoop.hive.ql.hooks.HookContext;
import org.apache.hadoop.security.UserGroupInformation;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.net.http.HttpClient;
import java.time.Duration;
import java.time.Instant;
import java.time.LocalDateTime;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.util.Map;

/**
 * Hive Query를 수집하는 Audit Hook
 *
 * @author KIM BYOUNG GON (support@data-dynamics.io)
 */
public class QueryAuditHook implements ExecuteWithHookContext {

    private static final Logger LOG = LoggerFactory.getLogger(ExecuteWithHookContext.class);

    private static final DateTimeFormatter formatter = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss.SSS");

    public static final String PROP_TARGET_URL = "QueryAuditHook.target.url";
    public static final String PROP_ENABLED = "QueryAuditHook.enabled";

    private HttpRequestHelper helper;

    public QueryAuditHook() {
        HttpClient client = HttpClient.newBuilder().version(HttpClient.Version.HTTP_2).connectTimeout(Duration.ofSeconds(3)).build();
        this.helper = new HttpRequestHelper(client);
    }

    @Override
    public void run(HookContext context) throws Exception {

        HiveConf conf = context.getConf();
        boolean isEnabled = conf.getBoolean(PROP_ENABLED, false); // 기본값 false
        if (!isEnabled) {
            LOG.debug("ConfigurableHook is disabled via configuration.");
            return;
        }

        String targetUrl = conf.getTrimmed(PROP_TARGET_URL, null); // 기본값 null, getTrimmed()는 앞뒤 공백 제거

        QueryPlan queryPlan = context.getQueryPlan();
        if (queryPlan == null) {
            LOG.warn("QueryPlan is null for hook type: {}", context.getHookType());
            return;
        }

        String queryId = queryPlan.getQueryId();
        String queryString = queryPlan.getQueryString();
        String shortUsername = getUser(context);
        String username = context.getUserName();
        String operationName = context.getOperationName();
        long eventTimestamp = System.currentTimeMillis();

        HookContext.HookType hookType = context.getHookType();

        switch (hookType) {
            case PRE_EXEC_HOOK: // 쿼리 시작 시점 기록 (QueryPlan에 기록된 시작 시각 사용)
                long queryStartTime = queryPlan.getQueryStartTime();
                String startTimeStr = formatTimestamp(queryStartTime);
                LOG.info("[PRE] QueryId: {}, Short Username: {}, Username: {}, Operation: {}, StartTime: {}, Query: {}", queryId, shortUsername, username, operationName, startTimeStr, queryString);
                break;

            case POST_EXEC_HOOK: // 쿼리 성공 종료 시점 및 소요 시간 기록
                long postStartTime = queryPlan.getQueryStartTime();
                long postEndTime = eventTimestamp; // Hook 호출 시점이 종료 시점 근사치
                long postDuration = (postStartTime > 0) ? (postEndTime - postStartTime) : -1;
                String postEndTimeStr = formatTimestamp(postEndTime);

                Map success = Map.of(
                        "queryId", queryId,
                        "shortUsername", shortUsername,
                        "username", username,
                        "startTime", String.valueOf(postStartTime),
                        "endTime", String.valueOf(postEndTime),
                        "durationMs", postDuration,
                        "query", queryString,
                        "status", "SUCCESS"
                );

                LOG.debug("Hive Query Audit을 송신할 메시지: {}", success);

                try {
                    helper.post(targetUrl, success, Map.class);
                    LOG.info("[SUCCESS] QueryId: {}, Short Username: {}, Username: {}, EndTime: {}, DurationMs: {}, Query: {}", queryId, shortUsername, username, postEndTimeStr, postDuration, queryString);
                } catch (Exception e) {
                    LOG.warn("Hive Query Audit을 송신할 수 없습니다. 원인: {}", e.getMessage(), e);
                }

                break;

            case ON_FAILURE_HOOK: // 쿼리 실패 시점 및 소요 시간, 에러 메시지 기록
                long failStartTime = queryPlan.getQueryStartTime();
                long failEndTime = eventTimestamp; // Hook 호출 시점이 실패 시점 근사치
                long failDuration = (failStartTime > 0) ? (failEndTime - failStartTime) : -1;
                String failEndTimeStr = formatTimestamp(failEndTime);
                String errorMsg = "N/A";
                if (context.getException() != null) {
                    errorMsg = context.getException().getMessage();
                }

                Map failed = Map.of(
                        "queryId", queryId,
                        "shortUsername", shortUsername,
                        "username", username,
                        "startTime", String.valueOf(failStartTime),
                        "endTime", String.valueOf(failEndTime),
                        "durationMs", failDuration,
                        "errorMsg", errorMsg,
                        "query", queryString,
                        "status", "FAILED"
                );

                LOG.debug("Hive Query Audit을 송신할 메시지: {}", failed);

                try {
                    helper.post(targetUrl, failed, Map.class);
                    LOG.warn("[FAILURE] QueryId: {}, Short Username: {}, Username: {}, EndTime: {}, DurationMs: {}, Error: {}, Query: {}", queryId, shortUsername, username, failEndTimeStr, failDuration, errorMsg, queryString);
                } catch(Exception e) {
                    LOG.warn("Hive Query Audit을 송신할 수 없습니다. 원인: {}", e.getMessage(), e);
                }

                break;

            default:
                // 다른 타입의 Hook (사용하지 않는 경우)
                break;
        }
    }

    private String getUser(HookContext hookContext) {
        UserGroupInformation ugi = hookContext.getUgi();
        return (ugi == null) ? "unknown" : ugi.getShortUserName();
    }

    private String formatTimestamp(long timestampMillis) {
        if (timestampMillis <= 0) return "N/A";
        return LocalDateTime.ofInstant(Instant.ofEpochMilli(timestampMillis), ZoneId.systemDefault()).format(formatter);
    }
}
