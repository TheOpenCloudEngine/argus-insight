package org.opencloudengine.argus.catalog.collector.hql.hook;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpRequest.BodyPublisher;
import java.net.http.HttpRequest.Builder;
import java.net.http.HttpResponse;

/**
 * HTTP 요청을 처리하기 위한 Helper 클래스.
 * RESTful API 호출을 위한 GET, POST, PUT, PATCH, DELETE 메소드를 제공합니다.
 *
 * @author KIM BYOUNG GON (support@data-dynamics.io)
 */
public class HttpRequestHelper {

    private final String APPLICATION_JSON = "application/json";
    private final String CONTENT_TYPE = "Content-Type";
    private final String AUTHORIZATION = "Authorization";
    private final String BEARER = "Bearer ";

    private final ObjectMapper objectMapper = new ObjectMapper().findAndRegisterModules();

    private final HttpClient httpClient;

    /**
     * HttpRequestHelper 생성자
     *
     * @param httpClient HTTP 요청을 수행할 HttpClient 인스턴스
     */
    public HttpRequestHelper(final HttpClient httpClient) {
        this.httpClient = httpClient;
    }

    /**
     * GET 요청을 수행합니다.
     *
     * @param url       요청할 URL
     * @param token     인증 토큰 (없는 경우 null)
     * @param valueType 응답 결과를 변환할 클래스 타입
     * @return 지정된 타입으로 변환된 응답 결과
     * @throws IOException          IO 예외 발생시
     * @throws InterruptedException 요청이 중단된 경우
     */
    public <T> T get(String url, String token, Class<T> valueType) throws IOException, InterruptedException {
        Builder builder = HttpRequest.newBuilder().GET().uri(URI.create(url));
        return send(valueType, token, builder);
    }

    /**
     * 토큰 없이 POST 요청을 수행합니다.
     *
     * @param uri       요청할 URI
     * @param request   요청 본문 객체
     * @param valueType 응답 결과를 변환할 클래스 타입
     * @return 지정된 타입으로 변환된 응답 결과
     * @throws IOException          IO 예외 발생시
     * @throws InterruptedException 요청이 중단된 경우
     */
    public <T> T post(String uri, Object request, Class<T> valueType)
            throws IOException, InterruptedException {
        return post(uri, request, valueType, null);
    }

    /**
     * 토큰과 함께 POST 요청을 수행합니다.
     *
     * @param uri       요청할 URI
     * @param request   요청 본문 객체
     * @param valueType 응답 결과를 변환할 클래스 타입
     * @param token     인증 토큰 (없는 경우 null)
     * @return 지정된 타입으로 변환된 응답 결과
     * @throws IOException          IO 예외 발생시
     * @throws InterruptedException 요청이 중단된 경우
     */
    public <T> T post(String uri, Object request, Class<T> valueType, String token) throws IOException, InterruptedException {
        Builder builder = HttpRequest.newBuilder().uri(URI.create(uri)).POST(getBodyPublisher(request)).header(CONTENT_TYPE, APPLICATION_JSON);
        return send(valueType, token, builder);
    }

    /**
     * PUT 요청을 수행합니다.
     *
     * @param uri       요청할 URI
     * @param request   요청 본문 객체
     * @param valueType 응답 결과를 변환할 클래스 타입
     * @param token     인증 토큰 (없는 경우 null)
     * @return 지정된 타입으로 변환된 응답 결과
     * @throws IOException          IO 예외 발생시
     * @throws InterruptedException 요청이 중단된 경우
     */
    public <T> T put(String uri, Object request, Class<T> valueType, String token) throws IOException, InterruptedException {
        Builder builder = HttpRequest.newBuilder().uri(URI.create(uri)).PUT(getBodyPublisher(request)).header(CONTENT_TYPE, APPLICATION_JSON);
        return send(valueType, token, builder);
    }

    /**
     * PATCH 요청을 수행합니다.
     *
     * @param uri       요청할 URI
     * @param valueType 응답 결과를 변환할 클래스 타입
     * @param token     인증 토큰 (없는 경우 null)
     * @return 지정된 타입으로 변환된 응답 결과
     * @throws IOException          IO 예외 발생시
     * @throws InterruptedException 요청이 중단된 경우
     */
    public <T> T patch(String uri, Class<T> valueType, String token) throws IOException, InterruptedException {
        Builder builder = HttpRequest.newBuilder().uri(URI.create(uri)).method("PATCH", HttpRequest.BodyPublishers.noBody()).header(CONTENT_TYPE, APPLICATION_JSON);
        return send(valueType, token, builder);
    }

    /**
     * DELETE 요청을 수행합니다.
     *
     * @param uri       요청할 URI
     * @param valueType 응답 결과를 변환할 클래스 타입
     * @param token     인증 토큰 (없는 경우 null)
     * @return 지정된 타입으로 변환된 응답 결과
     * @throws IOException          IO 예외 발생시
     * @throws InterruptedException 요청이 중단된 경우
     */
    public <T> T delete(String uri, Class<T> valueType, String token) throws IOException, InterruptedException {
        Builder builder = HttpRequest.newBuilder().uri(URI.create(uri)).DELETE();
        return send(valueType, token, builder);
    }

    /**
     * 요청 본문을 BodyPublisher로 변환합니다.
     *
     * @param request 변환할 요청 객체
     * @return 변환된 BodyPublisher
     * @throws JsonProcessingException JSON 변환 실패시
     */
    private BodyPublisher getBodyPublisher(Object request) throws JsonProcessingException {
        return HttpRequest.BodyPublishers.ofString(objectMapper.writeValueAsString(request));
    }

    /**
     * HTTP 요청을 실행하고 응답을 처리합니다.
     *
     * @param valueType 응답 결과를 변환할 클래스 타입
     * @param token     인증 토큰 (없는 경우 null)
     * @param builder   HTTP 요청 빌더
     * @return 지정된 타입으로 변환된 응답 결과
     * @throws IOException          IO 예외 발생시
     * @throws InterruptedException 요청이 중단된 경우
     */
    private <T> T send(Class<T> valueType, String token, Builder builder) throws IOException, InterruptedException {
        if (token != null) {
            builder.header(AUTHORIZATION, BEARER + token);
        }
        HttpResponse<String> response = httpClient.send(builder.build(), HttpResponse.BodyHandlers.ofString());
        if (response.statusCode() != 200) {
            throw new RuntimeException(response.body());
        }
        return objectMapper.readValue(response.body(), valueType);
    }
}
